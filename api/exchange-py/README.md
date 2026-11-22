# exchange-py

Microsserviço **Exchange** do Projeto Store em **Python/FastAPI**, sobre a
[PTAX do Banco Central do Brasil](https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/aplicacao#!/recursos)
(pública, sem chave). É o serviço da página
[API de Câmbio: serviço do BACEN](https://insper.github.io/platform/2026.2/exercises/exchange/bacen/)
da disciplina, com o mesmo contrato e algumas melhorias (validação da moeda, falha rápida,
cache negativo, busca em paralelo, métricas Prometheus). Documentação completa:
<https://eumiguelll.github.io/Projeto-PMA/projeto/exchange/>.

| Endpoint | Resposta |
|----------|----------|
| `GET /exchange/{from}/{to}` (e `/exchanges/...`) | `{"sell", "buy", "date", "id-account"}` + header `X-Cache: miss \| hit \| stale`; exige o header `id-account` (o gateway injeta) |
| `GET /exchange/currencies` | moedas que a PTAX cota, além do BRL |
| `GET /health` | `{"status": "ok"}` (probes e `HEALTHCHECK`) |
| `GET /metrics` | métricas Prometheus |
| `GET /exchange/docs` | Swagger UI |

Erros: código fora do formato de 3 letras ou sem `id-account` → `422`; moeda que a PTAX não
cota → `404`; PTAX fora e sem cotação guardada → `502`.

```bash
uv sync                                  # dependências + grupo dev (pytest, respx)
uv run pytest                            # 37 testes, PTAX simulada com respx (sem rede)
uv run pytest -m live -s                 # 2 testes contra a PTAX real (poucas chamadas)
uv run uvicorn main:app --reload --port 8000
curl -i -H "id-account: 0195ae95-5be7-7dd3-b35d-7a7d87c404fb" localhost:8000/exchange/USD/EUR

docker build -t exchange-py .            # python:3.12-slim + uv, uv sync --frozen --no-dev, usuário 10001
```

| Variável | Padrão | O que define |
|----------|--------|--------------|
| `PTAX_URL` | endereço do BCB | URL base da API OData da PTAX |
| `PTAX_TIMEOUT` | `3` | segundos de espera pela PTAX |
| `CACHE_SECONDS` | `300` | por quanto tempo uma cotação é reaproveitada |
| `RETRY_SECONDS` | `30` | depois de uma falha, por quanto tempo a PTAX não é chamada de novo (serve a cotação velha ou `502`) |

Manifests Kubernetes em `k8s/k8s.yaml`. Não faça teste de carga na PTAX: o cache existe para
que uma carga no gateway vire só algumas chamadas ao BCB (veja `ptax_requests_total` em
`/metrics` ou conte os `X-Cache: miss`).
