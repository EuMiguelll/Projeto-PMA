"""Exchange: cotações de câmbio pela PTAX do Banco Central do Brasil (BCB).

Parte do serviço da página "API de Câmbio: serviço do BACEN" da disciplina e mantém o mesmo
contrato: GET /exchange[s]/{from}/{to} -> {"sell", "buy", "date", "id-account"}, o header
X-Cache (miss | hit | stale), GET /exchange/currencies e GET /health. O que mudou:

- a moeda é validada (3 letras) antes de entrar na URL da PTAX: formato inválido -> 422;
- depois de uma falha da PTAX, a moeda fica RETRY_SECONDS sem nova chamada também quando
  não há cotação guardada (502 imediato, sem fila de requisições esperando o timeout);
- moeda desconhecida também fica em cache (404 sem chamar a PTAX de novo);
- as duas moedas do par são buscadas em paralelo, e o boletim mais recente é escolhido pela
  data (não pela posição na resposta);
- o 502 não expõe detalhes internos (eles vão para o log);
- métricas Prometheus em /metrics (mesmos nomes de métricas HTTP dos serviços Spring).
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import FastAPI, Header, HTTPException, Path, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, disable_created_metrics, generate_latest
from pydantic import BaseModel, ConfigDict, Field

PTAX_URL = os.getenv("PTAX_URL", "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata")
PTAX_TIMEOUT = float(os.getenv("PTAX_TIMEOUT", "3"))  # segundos: nunca esperar mais que quem chamou
CACHE_SECONDS = float(os.getenv("CACHE_SECONDS", "300"))  # a PTAX publica poucos boletins por dia
RETRY_SECONDS = float(os.getenv("RETRY_SECONDS", "30"))  # depois de uma falha, quanto esperar para tentar de novo
BRASILIA = timezone(timedelta(hours=-3))  # o Brasil não tem horário de verão desde 2019
CODE = r"^[A-Za-z]{3}$"  # ISO 4217; só isso entra na URL da PTAX (nada de aspas, & ou /)
BRL = {"buy": 1.0, "sell": 1.0, "date": None}  # a PTAX cota tudo em reais: o real vale 1

log = logging.getLogger("uvicorn.error")  # mesmo formato e destino dos logs do uvicorn

# métricas: as HTTP com os nomes do Micrometer, para o dashboard do Grafana somar o exchange
# aos serviços Spring sem mudar as consultas; as da PTAX contam quantas vezes o BCB foi chamado
disable_created_metrics()
HTTP_REQUESTS = Histogram("http_server_requests_seconds", "Requisições HTTP recebidas", ["method", "uri", "status"])
RATE_RESPONSES = Counter("exchange_rate_responses", "Cotações respondidas, pelo valor do header X-Cache", ["cache"])
PTAX_REQUESTS = Counter("ptax_requests", "Chamadas à PTAX do BCB, por resultado", ["outcome"])
PTAX_SECONDS = Histogram("ptax_request_duration_seconds", "Duração das chamadas à PTAX")


@dataclass(frozen=True)
class Entry:
    """O que se sabe de uma moeda até `until` (time.monotonic())."""

    until: float
    value: dict | list | None  # a cotação {"buy", "sell", "date"} (ou a lista de moedas); None se não há
    status: str  # hit (cotação nova) | stale (cotação velha após falha) | unknown (404) | down (502)


# moeda -> Entry, e um lock por moeda; com a validação de 3 letras, no máximo 26³ chaves
_cache: dict[str, Entry] = {}
_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=PTAX_TIMEOUT) as client:
        app.state.client = client
        yield


app = FastAPI(
    title="exchange",
    summary="Cotações de câmbio pela PTAX do Banco Central do Brasil",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/exchange/docs",  # pelo gateway (com login): /exchange/docs
    openapi_url="/exchange/openapi.json",
    redoc_url=None,
)


@app.middleware("http")
async def http_metrics(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # o template da rota (/exchange/{source}/{target}), não o caminho: cardinalidade fixa
        uri = getattr(request.scope.get("route"), "path", "UNKNOWN")
        HTTP_REQUESTS.labels(request.method, uri, str(status)).observe(time.perf_counter() - start)


def today() -> date:
    """Hoje em Brasília: a data que a PTAX usa nos boletins (o contêiner roda em UTC)."""
    return datetime.now(BRASILIA).date()


def _fresh(currency: str) -> Entry | None:
    entry = _cache.get(currency)
    return entry if entry and time.monotonic() < entry.until else None


def _answer(what: str, entry: Entry) -> tuple[dict | list, str]:
    if entry.status == "unknown":
        raise HTTPException(status_code=404, detail=f"Unknown currency: {what}")
    if entry.status == "down":
        raise HTTPException(status_code=502, detail=f"PTAX unavailable and nothing cached for {what}")
    return entry.value, entry.status


async def brl_quote(currency: str) -> tuple[dict, str]:
    """Última cotação PTAX da moeda em BRL ({"buy", "sell", "date"}) e de onde veio."""
    if currency == "BRL":
        return BRL, "hit"
    if entry := _fresh(currency):
        return _answer(currency, entry)
    # uma atualização por moeda de cada vez: quem chega enquanto isso espera por ela em vez
    # de chamar a PTAX junto (estouro de requisições num provedor que não é nosso)
    async with _locks[currency]:
        if entry := _fresh(currency):
            return _answer(currency, entry)
        return await _refresh(currency)


async def _refresh(currency: str) -> tuple[dict, str]:
    # 7 dias sempre contêm um dia útil (fim de semana e feriado não têm PTAX)
    end = today()
    start = end - timedelta(days=7)
    url = (
        f"{PTAX_URL}/CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
        f"?@moeda='{currency}'&@dataInicial='{start:%m-%d-%Y}'&@dataFinalCotacao='{end:%m-%d-%Y}'"
        "&$format=json&$select=cotacaoCompra,cotacaoVenda,dataHoraCotacao"
    )
    began = time.perf_counter()
    try:
        response = await app.state.client.get(url)
        response.raise_for_status()
        rows = response.json()["value"]
        quote = _latest(rows) if rows else None
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
        PTAX_REQUESTS.labels(outcome="error").inc()
        log.warning("PTAX falhou para %s: %r", currency, e)  # o detalhe fica no log, não na resposta
        # BCB lento, fora ou nos bloqueando: uma cotação velha é melhor que um erro; sem ela, 502.
        # Nos dois casos, a próxima tentativa só depois de RETRY_SECONDS (falha rápida até lá)
        old = _cache.get(currency)
        quote = old.value if old else None
        _cache[currency] = Entry(time.monotonic() + RETRY_SECONDS, quote, "stale" if quote else "down")
        return _answer(currency, _cache[currency])
    finally:
        PTAX_SECONDS.observe(time.perf_counter() - began)

    if quote is None:  # a PTAX respondeu, mas não cota essa moeda
        PTAX_REQUESTS.labels(outcome="not_found").inc()
        _cache[currency] = Entry(time.monotonic() + CACHE_SECONDS, None, "unknown")
        return _answer(currency, _cache[currency])
    PTAX_REQUESTS.labels(outcome="ok").inc()
    _cache[currency] = Entry(time.monotonic() + CACHE_SECONDS, quote, "hit")
    return quote, "miss"


def _latest(rows: list[dict]) -> dict:
    """O boletim mais recente da janela (abertura, intermediários e fechamento de cada dia)."""
    last = max(rows, key=lambda row: row["dataHoraCotacao"])
    buy, sell = float(last["cotacaoCompra"]), float(last["cotacaoVenda"])
    if buy <= 0 or sell <= 0:
        raise ValueError(f"cotação inválida: {last}")
    return {"buy": buy, "sell": sell, "date": last["dataHoraCotacao"][:19]}


Currency = Annotated[str, Path(pattern=CODE, description="Código ISO 4217 de 3 letras", examples=["USD"])]


class Rate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sell: float = Field(description="quanto o mercado cobra por 1 `from`, em `to`", examples=[0.910559])
    buy: float = Field(description="quanto o mercado paga por 1 `from`, em `to`", examples=[0.910357])
    date: str | None = Field(description="boletim PTAX usado (horário de Brasília)", examples=["2026-11-19 13:04:18"])
    id_account: str = Field(alias="id-account", description="conta autenticada (header do gateway)")


class CurrencyOut(BaseModel):
    symbol: str
    name: str


@app.get(
    "/exchange/{source}/{target}",
    response_model=Rate,
    responses={404: {"description": "moeda que a PTAX não cota"}, 502: {"description": "PTAX fora e sem cache"}},
)
@app.get("/exchanges/{source}/{target}", response_model=Rate, include_in_schema=False)
async def exchange(
    source: Currency,
    target: Currency,
    response: Response,
    id_account: Annotated[str, Header(alias="id-account", min_length=1)],
):
    """Cotação para converter 1 unidade de `source` em `target` (ex.: USD → EUR)."""
    (src, src_from), (tgt, tgt_from) = await _both(source.upper(), target.upper())
    # X-Cache: miss se a PTAX foi chamada, stale se uma cotação vencida foi usada, hit senão
    froms = {src_from, tgt_from}
    cache = "miss" if "miss" in froms else "stale" if "stale" in froms else "hit"
    response.headers["X-Cache"] = cache
    RATE_RESPONSES.labels(cache=cache).inc()
    # a PTAX cota tudo em BRL, então o par sai cruzado via BRL:
    # buy  = o que o mercado paga por 1 `source`, em `target` (compra source, vende target)
    # sell = o que o mercado cobra por 1 `source`, em `target` (vende source, compra target)
    dates = [d for d in (src["date"], tgt["date"]) if d]
    return {
        "sell": round(src["sell"] / tgt["buy"], 6),
        "buy": round(src["buy"] / tgt["sell"], 6),
        "date": max(dates) if dates else None,
        "id-account": id_account,
    }


async def _both(source: str, target: str) -> list[tuple[dict, str]]:
    """As duas moedas em paralelo; se as duas falharem, vale o erro da primeira (`source`)."""
    results = await asyncio.gather(brl_quote(source), brl_quote(target), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return results


_currencies: Entry | None = None
_currencies_lock = asyncio.Lock()


@app.get("/exchange/currencies", response_model=list[CurrencyOut])
async def currencies():
    """Moedas que a PTAX cota (além do BRL), com o mesmo cache das cotações."""
    global _currencies
    async with _currencies_lock:
        if _currencies and time.monotonic() < _currencies.until:
            return _answer("the currency list", _currencies)[0]
        try:
            response = await app.state.client.get(f"{PTAX_URL}/Moedas?$format=json&$select=simbolo,nomeFormatado")
            response.raise_for_status()
            listing = [{"symbol": m["simbolo"], "name": m["nomeFormatado"]} for m in response.json()["value"]]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
            PTAX_REQUESTS.labels(outcome="error").inc()
            log.warning("PTAX falhou na lista de moedas: %r", e)
            old = _currencies.value if _currencies else None
            _currencies = Entry(time.monotonic() + RETRY_SECONDS, old, "stale" if old else "down")
            return _answer("the currency list", _currencies)[0]
        PTAX_REQUESTS.labels(outcome="ok").inc()
        _currencies = Entry(time.monotonic() + CACHE_SECONDS, listing, "hit")
        return listing


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
