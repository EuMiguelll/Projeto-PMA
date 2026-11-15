# Visão geral e arquitetura

A arquitetura segue a da disciplina (hands-on 1–3): cada microsserviço Java tem um **módulo de
interface** (`account`, `auth`, `exchange` — contrato REST como interface `@FeignClient` + DTOs
em `record`) e um **módulo de serviço** executável (`*-service`) que implementa essa interface.
Assim, quem precisa chamar um serviço (ex.: o `auth-service` chamando o `account`) só depende
do jar da interface e o Feign gera o cliente HTTP.

## Componentes

```mermaid
flowchart LR
    internet([Internet]) -->|":80 / :8080"| gw
    subgraph trusted [Trusted layer — rede do compose / cluster]
        gw["gateway-service<br/>Spring Cloud Gateway<br/>JWT filter · rate limit"]
        auth["auth-service<br/>JWT (JJWT)<br/>circuit breaker"]
        account["account-service<br/>JPA · Flyway<br/>cache"]
        exchange["exchange-service<br/>RestClient<br/>cache · retry · CB"]
        db[(PostgreSQL 17)]
        redis[(Redis 7)]
        gw -->|/auth/**| auth
        gw -->|/accounts/**| account
        gw -->|/exchanges/**| exchange
        gw -->|POST /auth/solve| auth
        auth -->|Feign: /accounts/login, /accounts/:id| account
        account --> db
        account -.-> redis
        exchange -.-> redis
        gw -.-> redis
    end
    exchange -->|HTTPS| awesome[[AwesomeAPI]]
    subgraph obs [Observabilidade]
        prom[Prometheus] --> graf[Grafana]
    end
    prom -.scrape /*/actuator/prometheus.-> trusted
```

| Serviço | Pacote | Porta | Endpoints principais | Dependências |
|---------|--------|------:|----------------------|--------------|
| gateway | `store.gateway` | 8080 (única exposta) | `GET /health-check`, `GET /info`, rotas `/auth/**`, `/accounts/**`, `/exchanges/**` | auth, Redis |
| auth | `store.auth` | 8080 | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/solve`, `GET /auth/logout` | account |
| account | `store.account` | 8080 | `POST /accounts`, `GET /accounts`, `GET/DELETE /accounts/{id}`, `POST /accounts/login` | PostgreSQL, Redis |
| exchange | `store.exchange` | 8080 | `GET /exchanges/{from}/{to}` | AwesomeAPI, Redis |

Todos expõem `/<prefixo>/actuator/health/{liveness,readiness}` (probes do Kubernetes) e
`/<prefixo>/actuator/prometheus` (métricas), com o prefixo do próprio serviço como no hands-on 6.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Linguagem / framework | Java 25, Spring Boot 4.1.1, Spring Cloud 2025.1.3 |
| Gateway | Spring Cloud Gateway Server WebFlux (reativo, Netty) |
| Comunicação interna | OpenFeign (auth → account), RestClient (exchange → AwesomeAPI), WebClient (gateway → auth) |
| Segurança | JWT HS256 (JJWT 0.13) em cookie `HttpOnly`, validado no gateway |
| Persistência | PostgreSQL 17, Spring Data JPA, Flyway |
| Resiliência | Resilience4j 2.4 (circuit breaker, retry), rate limiter Redis do Spring Cloud Gateway |
| Cache | Redis 7 + Spring Cache |
| Observabilidade | Actuator + Micrometer → Prometheus → Grafana |
| Build | Maven Wrapper (`./mvnw`), Docker (`eclipse-temurin:25-jre`) |
| Orquestração | Docker Compose (local), Kubernetes / Amazon EKS |
| CI/CD | GitHub Actions → Amazon ECR (ou Docker Hub) → EKS |

## Fluxo de uma requisição autenticada

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant G as gateway
    participant A as auth
    participant C as account
    participant E as exchange
    participant R as Redis
    U->>G: POST /auth/login {email, password}
    G->>A: (rota aberta)
    A->>C: POST /accounts/login (Feign)
    C-->>A: AccountOut (ou 401)
    A-->>U: 200 + Set-Cookie: __store_jwt_token=<JWT>
    U->>G: GET /exchanges/USD/BRL (cookie)
    G->>R: rate limit (token bucket por IP)
    G->>A: POST /auth/solve {token}
    A-->>G: {idAccount}
    G->>E: GET /exchanges/USD/BRL + header id-account
    E->>R: cache exchanges::USD-BRL?
    alt miss
        E->>E: AwesomeAPI (retry + circuit breaker)
        E->>R: SET (TTL 60 s)
    end
    E-->>U: {"sell":5.668,"buy":5.6666,"date":"...","id-account":"..."}
```

O gateway **remove** qualquer header `id-account` vindo do cliente (`RemoveRequestHeader`) e só
o recoloca a partir do token validado — os serviços confiam nesse header sem precisar validar
JWT (testado no smoke test: um `id-account: hacker` forjado é descartado).

## Estrutura do repositório principal

```text
platform/
├── api/                      # submódulos (um repositório por módulo)
│   ├── account/  account-service/
│   ├── auth/     auth-service/
│   ├── exchange/ exchange-service/
│   └── gateway-service/
├── aws/                      # eks-create.sh, rds-create.sh, eks-teardown.sh, template da VPC
├── k8s/                      # postgres.yaml, redis.yaml, ingress.yaml, deploy.sh
├── load-test/                # busybox.sh (enunciado), k6.js, README (roteiro do vídeo)
├── setup/                    # prometheus.yml, provisionamento do Grafana (datasource + dashboard)
├── scripts/                  # build.sh, smoke-test.sh, push-images.sh
├── presentation/slides.md    # slides (Marp)
├── docs/ + mkdocs.yml        # esta documentação
├── compose.yaml
├── AWS_RUNBOOK.md
└── publish.sh                # cria os repositórios no GitHub e faz o push
```

Cada repositório de serviço contém: código, testes, `Dockerfile`, `k8s/k8s.yaml` (como pede o
exercício MiniKube) e `.github/workflows/ci.yml`.
