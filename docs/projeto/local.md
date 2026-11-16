# Execução local

Tudo roda na máquina com Docker — inclusive o build, se não houver Java instalado: o
`scripts/build.sh` executa o **Maven Wrapper** (`./mvnw`) de cada módulo dentro de um container
`eclipse-temurin:25-jdk`, um módulo por vez (interfaces primeiro, com `install`; depois os
serviços, com `package`, que roda os testes).

```bash
git clone --recurse-submodules https://github.com/EuMiguelll/Projeto-PMA.git && cd Projeto-PMA
./scripts/build.sh                 # 7 módulos: compila, testa e gera api/*-service/target/*.jar
docker compose up -d --build       # db, redis, account, auth, exchange, gateway, prometheus, grafana
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

Como no hands-on 2, só o gateway publica porta: `account`, `auth`, `exchange`, `db` e `redis`
ficam na rede interna do compose (trusted layer). Os serviços Java têm limite de 512 MiB e a JVM
usa `-XX:MaxRAMPercentage=75`.

## Build e testes

```console
$ ./scripts/build.sh
==> account            BUILD SUCCESS
==> auth               BUILD SUCCESS
==> exchange           BUILD SUCCESS
==> account-service    Tests run: 4, Failures: 0, Errors: 0   BUILD SUCCESS
==> auth-service       Tests run: 4, Failures: 0, Errors: 0   BUILD SUCCESS
==> exchange-service   Tests run: 1, Failures: 0, Errors: 0   BUILD SUCCESS
==> gateway-service    Tests run: 2, Failures: 0, Errors: 0   BUILD SUCCESS
```

No Mac o script respeita a carga da máquina: só compila com *load average* < 5 e pressão de
memória normal, com prioridade baixa (`taskpolicy -b`), `-T 2` e no máximo 2 CPUs / 3 GB para o
container do Maven.

## Smoke test

`scripts/smoke-test.sh [URL]` (padrão `http://localhost:8080`; no EKS, passe o DNS do ELB):

```console
$ ./scripts/smoke-test.sh
✅ GET /health-check (aberto) -> 200
✅ GET /info (aberto) -> 200
✅ POST /auth/register -> 200
✅ POST /auth/register (email repetido) -> 409
✅ POST /auth/login (senha errada) -> 401
✅ POST /auth/login devolve cookie JWT -> yes
✅ GET /accounts sem cookie -> 401
✅ GET /accounts com token forjado -> 401
✅ GET /auth/me -> smoke.1794773024@insper.edu.br
✅ GET /accounts/{id} (1ª vez: banco) -> 200
✅ GET /accounts/{id} (2ª vez: cache Redis) -> 200
   exchange: {"sell":5.668,"buy":5.6666,"date":"2026-11-13 18:30:13","id-account":"7586833b-189d-4f47-a27d-0cf8589a8b3b"}
✅ GET /exchanges/USD/BRL tem sell/buy -> yes
✅ id-account vem do token (header forjado descartado) -> 7586833b-189d-4f47-a27d-0cf8589a8b3b
✅ GET /exchanges/XXX/YYY (par inválido) -> 404
SMOKE TEST OK
```

O mesmo fluxo roda no GitHub Actions a cada push no repositório principal (workflow **E2E**).

## Testando à mão

```bash
curl -X POST localhost:8080/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Antonio do Estudo","email":"acme@insper.edu.br","password":"123@321"}'
curl -c cookies.txt -X POST localhost:8080/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"acme@insper.edu.br","password":"123@321"}'
curl -b cookies.txt localhost:8080/auth/me
curl -b cookies.txt localhost:8080/exchanges/USD/BRL
curl -i localhost:8080/accounts            # 401 sem cookie
```
