"""Smoke contra a PTAX REAL (olinda.bcb.gov.br): fica fora do `pytest` padrão.

    uv run pytest -m live -v

Poucas chamadas (uma por moeda e a lista de moedas), nunca em laço: a PTAX é um serviço
público do BCB e não deve receber teste de carga.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from conftest import ACCOUNT

pytestmark = pytest.mark.live


@pytest.fixture
def real():
    main._cache.clear()
    main._locks.clear()
    with TestClient(main.app, headers={"id-account": ACCOUNT}) as c:
        yield c


def test_real_ptax_cross_rate_and_cache(real):
    miss = real.get("/exchange/USD/EUR")
    hit = real.get("/exchange/USD/EUR")
    print("\nGET /exchange/USD/EUR ->", miss.status_code, miss.headers["X-Cache"], miss.text)

    assert miss.status_code == 200
    assert [miss.headers["X-Cache"], hit.headers["X-Cache"]] == ["miss", "hit"]
    body = miss.json()
    assert 0 < body["buy"] <= body["sell"]
    assert body["id-account"] == ACCOUNT
    # o boletim usado é de no máximo 7 dias atrás (a janela que o serviço consulta)
    bulletin = datetime.strptime(body["date"], "%Y-%m-%d %H:%M:%S")
    assert datetime.now(main.BRASILIA).replace(tzinfo=None) - bulletin < timedelta(days=8)


def test_real_ptax_dollar_unknown_currency_and_list(real):
    usd = real.get("/exchange/USD/BRL")
    print("\nGET /exchange/USD/BRL ->", usd.status_code, usd.text)
    assert usd.status_code == 200
    assert 1 < usd.json()["sell"] < 20

    assert real.get("/exchange/XYZ/BRL").status_code == 404

    symbols = {c["symbol"] for c in real.get("/exchange/currencies").json()}
    assert {"USD", "EUR", "GBP", "JPY"} <= symbols
