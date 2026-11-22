"""Contrato do Exchange (o do enunciado e o da página do BACEN), com a PTAX simulada."""

import asyncio

import httpx
import pytest

import main
from conftest import ACCOUNT

USD_BUY, USD_SELL = 5.8883, 5.8889  # fechamento de 19/11/2026
EUR_BUY, EUR_SELL = 6.4659, 6.4672


# --- cotação --------------------------------------------------------------------------------


def test_usd_eur_is_a_cross_rate_through_brl(client):
    r = client.get("/exchange/USD/EUR")

    assert r.status_code == 200
    assert r.headers["X-Cache"] == "miss"
    # sell = venda do USD / compra do EUR; buy = compra do USD / venda do EUR
    assert r.json() == {
        "sell": round(USD_SELL / EUR_BUY, 6),
        "buy": round(USD_BUY / EUR_SELL, 6),
        "date": "2026-11-19 13:04:18",
        "id-account": ACCOUNT,
    }
    assert r.json()["sell"] == 0.910763 and r.json()["buy"] == 0.910487


def test_formula_direction_with_round_numbers(client, ptax):
    ptax.rows = {
        "USD": [{"cotacaoCompra": 5.0, "cotacaoVenda": 5.1, "dataHoraCotacao": "2026-11-19 13:00:00.0"}],
        "EUR": [{"cotacaoCompra": 6.0, "cotacaoVenda": 6.2, "dataHoraCotacao": "2026-11-19 13:00:00.0"}],
    }
    body = client.get("/exchange/USD/EUR").json()
    assert (body["sell"], body["buy"]) == (0.85, 0.806452)  # 5.1 / 6.0 e 5.0 / 6.2
    assert body["sell"] > body["buy"]  # o mercado cobra mais do que paga


def test_usd_brl_is_the_ptax_quote_of_the_dollar(client, ptax):
    body = client.get("/exchange/USD/BRL").json()

    assert (body["sell"], body["buy"]) == (USD_SELL, USD_BUY)
    assert ptax.calls == ["USD"]  # o real vale 1: só o dólar vai à PTAX


def test_brl_usd_is_the_inverse(client):
    body = client.get("/exchange/BRL/USD").json()

    assert body["sell"] == round(1 / USD_BUY, 6)
    assert body["buy"] == round(1 / USD_SELL, 6)
    assert body["date"] == "2026-11-19 13:04:18"


def test_plural_route_of_the_exercise_statement_answers_the_same(client):
    assert client.get("/exchanges/USD/EUR").json() == client.get("/exchange/USD/EUR").json()


def test_codes_are_case_insensitive(client, ptax):
    assert client.get("/exchange/usd/eur").json() == client.get("/exchange/USD/EUR").json()
    assert ptax.calls == ["USD", "EUR"]  # a mesma entrada de cache


def test_latest_bulletin_is_chosen_by_date_not_by_position(client, ptax):
    ptax.rows["USD"] = list(reversed(ptax.rows["USD"]))

    body = client.get("/exchange/USD/BRL").json()
    assert (body["sell"], body["date"]) == (USD_SELL, "2026-11-19 13:04:18")


def test_weekend_after_holiday_uses_the_last_bulletin_of_a_7_day_window(client, ptax):
    # domingo, 22/11/2026: sexta (20/11) foi feriado; o último boletim é o fechamento de quinta
    body = client.get("/exchange/USD/BRL").json()

    assert ptax.windows == [("11-15-2026", "11-22-2026")]
    assert body["date"] == "2026-11-19 13:04:18"
    assert body["sell"] == USD_SELL  # o fechamento, não o intermediário do mesmo segundo


# --- erros ----------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/exchange/XYZ/BRL", "/exchange/USD/XYZ", "/exchanges/XXX/YYY"])
def test_unknown_currency_is_404(client, path):
    r = client.get(path)

    assert r.status_code == 404
    assert r.json()["detail"].startswith("Unknown currency: ")


def test_unknown_currency_is_cached_too(client, ptax):
    assert client.get("/exchange/XYZ/BRL").status_code == 404
    assert client.get("/exchange/XYZ/BRL").status_code == 404
    assert ptax.calls == ["XYZ"]


def test_without_id_account_header_is_422(client, ptax):
    r = client.get("/exchange/USD/EUR", headers={"id-account": ""})
    assert r.status_code == 422

    del client.headers["id-account"]
    r = client.get("/exchange/USD/EUR")
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["header", "id-account"]
    assert ptax.calls == []


@pytest.mark.parametrize("code", ["US", "USDT", "U1D", "US$", "U'D", "U&D"])
def test_malformed_code_is_422_and_never_reaches_ptax(client, ptax, code):
    r = client.get(f"/exchange/{code}/BRL")

    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["path", "source"]
    assert ptax.calls == []  # nada de aspas ou & na URL OData


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectTimeout("timeout"),
        httpx.ConnectError("connection refused"),
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(429, text="Too Many Requests"),
        httpx.Response(200, text="<html>manutenção</html>"),
        httpx.Response(200, json={"unexpected": []}),
    ],
    ids=["timeout", "refused", "500", "429", "html", "no-value"],
)
def test_ptax_down_without_cache_is_502_without_internal_details(client, ptax, failure):
    ptax.failure = failure

    r = client.get("/exchange/USD/BRL")

    assert r.status_code == 502
    assert r.json() == {"detail": "PTAX unavailable and nothing cached for USD"}
    assert "olinda" not in r.text and "Error" not in r.text


def test_after_a_failure_without_cache_it_fails_fast_for_retry_seconds(client, ptax):
    ptax.failure = httpx.ConnectTimeout("timeout")
    assert client.get("/exchange/USD/BRL").status_code == 502

    ptax.failure = None  # a PTAX voltou, mas a janela de RETRY_SECONDS (30 s) ainda não passou
    assert client.get("/exchange/USD/BRL").status_code == 502
    assert ptax.calls == ["USD"]  # sem fila de requisições esperando o timeout


# --- cache ----------------------------------------------------------------------------------


def test_second_request_is_a_cache_hit(client, ptax):
    first = client.get("/exchange/USD/EUR")
    second = client.get("/exchange/USD/EUR")

    assert [first.headers["X-Cache"], second.headers["X-Cache"]] == ["miss", "hit"]
    assert first.json() == second.json()
    assert ptax.calls == ["USD", "EUR"]


def test_pairs_share_the_cache_per_currency(client, ptax):
    client.get("/exchange/USD/EUR")
    r = client.get("/exchange/EUR/USD")

    assert r.headers["X-Cache"] == "hit"
    assert ptax.calls == ["USD", "EUR"]


def test_expired_rate_is_fetched_again(client, ptax, monkeypatch):
    monkeypatch.setattr(main, "CACHE_SECONDS", 0)

    client.get("/exchange/USD/BRL")
    r = client.get("/exchange/USD/BRL")

    assert r.headers["X-Cache"] == "miss"
    assert ptax.calls == ["USD", "USD"]


def test_ptax_down_with_cache_serves_the_stale_rate(client, ptax, monkeypatch):
    monkeypatch.setattr(main, "CACHE_SECONDS", 0)  # a cotação vence na hora
    fresh = client.get("/exchange/USD/EUR")
    ptax.failure = httpx.ConnectTimeout("timeout")

    stale = client.get("/exchange/USD/EUR")

    assert stale.status_code == 200
    assert stale.headers["X-Cache"] == "stale"
    assert stale.json() == fresh.json()

    ptax.failure = None  # dentro de RETRY_SECONDS continua stale, sem chamar a PTAX
    assert client.get("/exchange/USD/EUR").headers["X-Cache"] == "stale"
    assert ptax.calls == ["USD", "EUR", "USD", "EUR"]


def test_stale_rate_is_refreshed_after_retry_seconds(client, ptax, monkeypatch):
    monkeypatch.setattr(main, "CACHE_SECONDS", 0)
    monkeypatch.setattr(main, "RETRY_SECONDS", 0)
    client.get("/exchange/USD/BRL")
    ptax.failure = httpx.ConnectTimeout("timeout")
    assert client.get("/exchange/USD/BRL").headers["X-Cache"] == "stale"

    ptax.failure = None
    ptax.rows["USD"].append({"cotacaoCompra": 5.9, "cotacaoVenda": 5.91, "dataHoraCotacao": "2026-11-20 10:00:00.0"})
    r = client.get("/exchange/USD/BRL")

    assert r.headers["X-Cache"] == "miss"
    assert r.json()["sell"] == 5.91


@pytest.mark.anyio
async def test_concurrent_requests_make_a_single_call_per_currency(ptax):
    ptax.delay = 0.05  # a PTAX demora: as requisições se sobrepõem
    transport = httpx.ASGITransport(app=main.app)
    async with main.lifespan(main.app), httpx.AsyncClient(transport=transport, base_url="http://exchange") as c:
        responses = await _gather(c, 20)

    assert {r.status_code for r in responses} == {200}
    assert sorted(ptax.calls) == ["EUR", "USD"]  # 20 requisições, 2 chamadas à PTAX
    assert len({r.text for r in responses}) == 1
    assert [r.headers["X-Cache"] for r in responses].count("miss") >= 1


async def _gather(c: httpx.AsyncClient, n: int) -> list[httpx.Response]:
    return await asyncio.gather(*(c.get("/exchange/USD/EUR", headers={"id-account": ACCOUNT}) for _ in range(n)))


# --- moedas, health e métricas --------------------------------------------------------------


def test_currencies_lists_what_ptax_quotes_and_is_cached(client, ptax):
    first = client.get("/exchange/currencies")
    second = client.get("/exchange/currencies")

    assert first.status_code == 200
    assert first.json() == [{"symbol": "EUR", "name": "Euro"}, {"symbol": "USD", "name": "Dólar dos Estados Unidos"}]
    assert second.json() == first.json()
    assert ptax.calls == ["Moedas"]


def test_currencies_without_ptax_and_cache_is_502(client, ptax):
    ptax.failure = httpx.ConnectTimeout("timeout")

    r = client.get("/exchange/currencies")

    assert r.status_code == 502
    assert r.json() == {"detail": "PTAX unavailable and nothing cached for the currency list"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_metrics_count_ptax_calls_and_x_cache(client):
    def value(text: str, sample: str) -> float:
        line = next((x for x in text.splitlines() if x.startswith(sample + " ")), None)
        return float(line.split()[-1]) if line else 0.0

    samples = [
        'ptax_requests_total{outcome="ok"}',
        'exchange_rate_responses_total{cache="miss"}',
        'exchange_rate_responses_total{cache="hit"}',
    ]
    before = client.get("/metrics").text
    client.get("/exchange/USD/EUR")
    client.get("/exchange/USD/EUR")
    after = client.get("/metrics").text

    # 2 chamadas à PTAX (USD e EUR), 1 resposta miss e 1 hit
    assert [value(after, s) - value(before, s) for s in samples] == [2, 1, 1]
    # mesmo nome do Micrometer, com o template da rota (não o caminho com as moedas)
    assert 'http_server_requests_seconds_count{method="GET",status="200",uri="/exchange/{source}/{target}"}' in after
    assert "/exchange/USD/EUR" not in after


def test_openapi_documents_the_contract(client):
    spec = client.get("/exchange/openapi.json").json()

    assert "/exchange/{source}/{target}" in spec["paths"]
    assert set(spec["components"]["schemas"]["Rate"]["properties"]) == {"sell", "buy", "date", "id-account"}
