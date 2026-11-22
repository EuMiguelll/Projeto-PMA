"""PTAX simulada com respx: nenhum teste sai para a rede (os marcados com `live` ficam à parte)."""

import asyncio
from datetime import date, datetime

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import main

ACCOUNT = "0195ae95-5be7-7dd3-b35d-7a7d87c404fb"
SUNDAY = date(2026, 11, 22)  # domingo depois do feriado de 20/11: o último boletim é o de quinta, 19/11

# boletins reais da PTAX (olinda.bcb.gov.br), em BRL, como o OData devolve com o $select do serviço
BULLETINS = {
    "USD": [
        {"cotacaoCompra": 5.7318, "cotacaoVenda": 5.7324, "dataHoraCotacao": "2026-11-16 13:06:32.509132"},
        {"cotacaoCompra": 5.8895, "cotacaoVenda": 5.8901, "dataHoraCotacao": "2026-11-19 10:11:10.714595"},
        {"cotacaoCompra": 5.9095, "cotacaoVenda": 5.9101, "dataHoraCotacao": "2026-11-19 13:04:18.300772"},
        {"cotacaoCompra": 5.8883, "cotacaoVenda": 5.8889, "dataHoraCotacao": "2026-11-19 13:04:18.325373"},
    ],
    "EUR": [
        {"cotacaoCompra": 6.4767, "cotacaoVenda": 6.4779, "dataHoraCotacao": "2026-11-19 10:11:10.714595"},
        {"cotacaoCompra": 6.4892, "cotacaoVenda": 6.4905, "dataHoraCotacao": "2026-11-19 13:04:18.300772"},
        {"cotacaoCompra": 6.4659, "cotacaoVenda": 6.4672, "dataHoraCotacao": "2026-11-19 13:04:18.325373"},
    ],
}
CURRENCIES = [
    {"simbolo": "EUR", "nomeFormatado": "Euro"},
    {"simbolo": "USD", "nomeFormatado": "Dólar dos Estados Unidos"},
]


class FakePTAX:
    """Imita CotacaoMoedaPeriodo e Moedas; `failure` faz a próxima chamada falhar."""

    def __init__(self):
        self.rows = {currency: list(rows) for currency, rows in BULLETINS.items()}
        self.failure: Exception | httpx.Response | None = None
        self.delay = 0.0  # segundos: para os testes de concorrência
        self.calls: list[str] = []  # moedas pedidas, na ordem
        self.windows: list[tuple[str, str]] = []  # (dataInicial, dataFinalCotacao) de cada chamada

    async def cotacao(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        currency = params["@moeda"].strip("'")
        start, end = params["@dataInicial"].strip("'"), params["@dataFinalCotacao"].strip("'")
        self.calls.append(currency)
        self.windows.append((start, end))
        if failure := await self._fail(request):
            return failure
        first = datetime.strptime(start, "%m-%d-%Y").date()
        last = datetime.strptime(end, "%m-%d-%Y").date()
        rows = [
            r for r in self.rows.get(currency, []) if first <= date.fromisoformat(r["dataHoraCotacao"][:10]) <= last
        ]
        return httpx.Response(200, json={"@odata.context": "fake", "value": rows})

    async def moedas(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("Moedas")
        if failure := await self._fail(request):
            return failure
        return httpx.Response(200, json={"@odata.context": "fake", "value": CURRENCIES})

    async def _fail(self, request: httpx.Request) -> httpx.Response | None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.failure, Exception):
            raise type(self.failure)(str(self.failure), request=request)
        return self.failure


@pytest.fixture
def ptax(monkeypatch) -> FakePTAX:
    monkeypatch.setattr(main, "today", lambda: SUNDAY)
    # estado do processo zerado a cada teste (cache, locks e lista de moedas)
    main._cache.clear()
    main._locks.clear()
    monkeypatch.setattr(main, "_currencies", None)
    monkeypatch.setattr(main, "_currencies_lock", asyncio.Lock())
    fake = FakePTAX()
    # assert_all_mocked (padrão): qualquer chamada fora destas rotas falha o teste
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith=f"{main.PTAX_URL}/CotacaoMoedaPeriodo(").mock(side_effect=fake.cotacao)
        router.get(url__startswith=f"{main.PTAX_URL}/Moedas?").mock(side_effect=fake.moedas)
        yield fake


@pytest.fixture
def client(ptax) -> TestClient:
    with TestClient(main.app, headers={"id-account": ACCOUNT}) as c:  # o gateway injeta esse header
        yield c


@pytest.fixture
def anyio_backend():
    return "asyncio"
