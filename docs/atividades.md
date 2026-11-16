# Atividades (roteiros)

A entrega pede a documentação e o código **das atividades feitas** ao longo da disciplina, além
do projeto. Esta página liga cada exercício da disciplina ao que foi entregue.

| Exercício | Status | Onde está |
|-----------|--------|-----------|
| **Exchange API** | ✅ | `exchange` + `exchange-service` — [Exchange](projeto/exchange.md). O exercício pede FastAPI/Python; no projeto foi feito em Java (justificativa na página) |
| **Bottlenecks** | ✅ | 6 bottlenecks implementados e medidos — [Bottlenecks](projeto/bottlenecks.md) |
| **MiniKube** | ✅ | `k8s/k8s.yaml` em cada repositório de serviço; implantado num cluster local (kind) com smoke test 14/14 e HPA — [Teste de carga](projeto/load-testing.md#resultado-no-kubernetes-local-kind) |
| **Jenkins** | ↪︎ GitHub Actions | a rubrica aceita *Jenkins **ou** GitHub Actions*; usamos o GitHub Actions com as mesmas etapas do exercício (SCM → dependências → build → imagem → deploy no K8s) — [CI/CD](projeto/cicd.md) |
| **Product API** | — | não feito: fora da rubrica do projeto 2026.2, que pede gateway, auth, account e exchange |
| **Order API** | — | idem |
| **Projeto** | ✅ | [Projeto](projeto/index.md) |

!!! note "Escopo"
    A rubrica do projeto 2026.2 é formada por gateway, auth, account, exchange, bottlenecks, AWS,
    EKS, CI/CD (Jenkins ou GitHub Actions), teste de carga, custos e documentação. Os exercícios
    Product e Order estão na lista de exercícios da disciplina, mas não entram na rubrica do projeto
    e não foram feitos por nós.

## Hands-on usados como referência

Os roteiros de hands-on da disciplina (account, auth, gateway, Docker, Kubernetes, observabilidade e
cache) foram a base do código do projeto; as escolhas que seguem cada um estão comentadas nas
páginas dos serviços:

- módulos de **interface** (`@FeignClient` + `record`) separados da implementação — [Visão geral](projeto/index.md);
- `account-service` com JPA + Flyway no schema `accounts` — [Account](projeto/account.md);
- `auth-service` emitindo JWT em cookie e o `AuthorizationFilter` do gateway — [Auth](projeto/auth.md), [Gateway](projeto/gateway.md);
- `Dockerfile` com `eclipse-temurin:25-jre` e `compose.yaml` com Postgres — [Execução local](projeto/local.md);
- Actuator com prefixo por serviço + Prometheus + Grafana — [Bottlenecks › Observabilidade](projeto/bottlenecks.md);
- cache Redis com Spring Cache — [Bottlenecks › Cache](projeto/bottlenecks.md).
