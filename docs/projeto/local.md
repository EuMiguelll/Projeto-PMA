# Execução local

Tudo roda na máquina com Docker — inclusive o build, se não houver Java ou uv instalado: o
`scripts/build.sh` executa o **Maven Wrapper** (`./mvnw`) de cada módulo Java dentro de um
container `eclipse-temurin:25-jdk`, um módulo por vez (interfaces primeiro, com `install`; depois
os serviços, com `package`, que roda os testes), e o **uv** + **pytest** do `exchange-py` (no
host ou num container `ghcr.io/astral-sh/uv`). A imagem do `exchange-py` é construída pelo
próprio `docker compose` (o `uv sync --frozen` roda no `Dockerfile`).

```bash
git clone --recurse-submodules https://github.com/EuMiguelll/Projeto-PMA.git && cd Projeto-PMA
./scripts/build.sh                 # 7 módulos Java (api/*-service/target/*.jar) + testes do exchange-py
docker compose up -d --build       # db, redis, account, auth, exchange (Python), gateway, prometheus, grafana
./scripts/smoke-test.sh            # teste ponta a ponta pelo gateway
docker compose down                # (-v para apagar o volume do Postgres)
```

| URL | O quê |
|-----|-------|
| <http://localhost:8080/info> | gateway (única porta da API exposta) |
| <http://localhost:9090> | Prometheus (Status → Targets) |
| <http://localhost:3000> | Grafana (admin/admin) → dashboard *Store — Bottlenecks* |

??? example "compose.yaml"

    ```yaml
    --8<-- "compose.yaml"
    ```

Como no hands-on 2, só o gateway publica porta: `account`, `auth`, `exchange` (porta 8000),
`db` e `redis` ficam na rede interna do compose (trusted layer). Os serviços Java têm limite de
512 MiB e a JVM usa `-XX:MaxRAMPercentage=75`; o `exchange-py` tem 256 MiB (sob o tráfego do smoke test, usa ~42 MiB).

## Build e testes

```console
$ ./scripts/build.sh
==> account            BUILD SUCCESS
==> auth               BUILD SUCCESS
==> exchange           BUILD SUCCESS
==> account-service    Tests run: 4, Failures: 0, Errors: 0   BUILD SUCCESS
==> auth-service       Tests run: 4, Failures: 0, Errors: 0   BUILD SUCCESS
==> exchange-service   Tests run: 3, Failures: 0, Errors: 0   BUILD SUCCESS   # versão anterior (Java)
==> gateway-service    Tests run: 4, Failures: 0, Errors: 0   BUILD SUCCESS
==> exchange-py        37 passed, 2 deselected                               # uv + pytest
```

(22/11/2026, JDK Temurin 25 e uv 0.11; os 2 testes *deselected* são os `live`, que chamam a PTAX
real e rodam à parte com `uv run pytest -m live`.)

No Mac o script respeita a carga da máquina: só compila com *load average* < 5 e pressão de
memória normal, com prioridade baixa (`taskpolicy -b`), `-T 2` e no máximo 2 CPUs / 3 GB para o
container do Maven.

## Smoke test

`scripts/smoke-test.sh [URL]` (padrão `http://localhost:8080`; no EKS, passe o DNS do ELB):

```console
$ ./scripts/smoke-test.sh   # 22/11/2026, exchange-py com a PTAX real
✅ GET /health-check (aberto) -> 200
✅ GET /info (aberto) -> 200
✅ POST /auth/register -> 200
✅ POST /auth/register (email repetido) -> 409
✅ POST /auth/login (senha errada) -> 401
✅ POST /auth/login devolve cookie JWT -> yes
✅ GET /accounts sem cookie -> 401
✅ GET /accounts com token forjado -> 401
✅ GET /auth/me -> smoke.1795318110@insper.edu.br
✅ GET /accounts/{id} (1ª vez: banco) -> 200
✅ GET /accounts/{id} (2ª vez: cache Redis) -> 200
   exchange: {"sell":5.8889,"buy":5.8883,"date":"2026-11-19 13:04:18","id-account":"03de49c7-21c8-4690-8751-41c7da3ef319"}
✅ GET /exchanges/USD/BRL tem sell/buy -> yes
✅ id-account vem do token (header forjado descartado) -> 03de49c7-21c8-4690-8751-41c7da3ef319
✅ GET /exchanges/USD/BRL de novo (cache em memória) -> hit
   exchange: {"sell":0.910763,"buy":0.910487,"date":"2026-11-19 13:04:18","id-account":"03de49c7-21c8-4690-8751-41c7da3ef319"}
✅ GET /exchange/USD/EUR (cruzada via BRL, sell >= buy) -> yes
✅ GET /exchange/USD/EUR sem cookie -> 401
✅ GET /exchanges/XXX/YYY (moeda desconhecida) -> 404
✅ GET /exchanges/US/BRL (código inválido) -> 422
SMOKE TEST OK
```

O mesmo fluxo roda no workflow **E2E** do GitHub Actions, com o stub da PTAX no lugar do BCB
([CI/CD](cicd.md#e2e-hermetico)). As 7 verificações do exchange cobrem as duas rotas
(`/exchanges/**` do enunciado e `/exchange/**` da página do BACEN), o `id-account` vindo do
token, o cache (`X-Cache: hit`) e os erros `401`, `404` e `422`.

## Testando à mão

```bash
curl -X POST localhost:8080/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Antonio do Estudo","email":"acme@insper.edu.br","password":"123@321"}'
curl -c cookies.txt -X POST localhost:8080/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"acme@insper.edu.br","password":"123@321"}'
curl -b cookies.txt localhost:8080/auth/me
curl -b cookies.txt localhost:8080/exchanges/USD/BRL
curl -i -b cookies.txt localhost:8080/exchange/USD/EUR   # header X-Cache: miss, depois hit
curl -b cookies.txt localhost:8080/exchange/currencies
curl -i localhost:8080/accounts            # 401 sem cookie
```
