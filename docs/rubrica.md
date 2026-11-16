# Checklist da rubrica

Cada item da [rubrica do projeto](https://insper.github.io/platform/2026.2/exercises/project/) e
da [entrega](https://insper.github.io/platform/2026.2/exercises/project/presentation/), com o que
foi feito e onde está a evidência.

## Rubrica do projeto (peso)

| Item | Peso | O que entregamos | Evidência |
|------|-----:|------------------|-----------|
| **Gateway** | 5 % | Spring Cloud Gateway (WebFlux): rotas, filtro JWT que chama `POST /auth/solve`, remove o `id-account` vindo do cliente, rate limiting no Redis | [Gateway](projeto/gateway.md) · [`gateway-service`](https://github.com/canavero/gateway-service) |
| **Auth** | 5 % | registro, login com JWT em cookie `HttpOnly`, `/auth/me`, `/auth/solve`; circuit breaker para o account | [Auth](projeto/auth.md) · [`auth`](https://github.com/canavero/auth) + [`auth-service`](https://github.com/canavero/auth-service) |
| **Account** | 5 % | CRUD de contas, JPA + Flyway no PostgreSQL, senha com hash, cache Redis | [Account](projeto/account.md) · [`account`](https://github.com/canavero/account) + [`account-service`](https://github.com/canavero/account-service) |
| **Exchange** | 5 % | cotações do PTAX do BACEN com cache, retry e circuit breaker; `id-account` vindo do token | [Exchange](projeto/exchange.md) · [`exchange`](https://github.com/canavero/exchange) + [`exchange-service`](https://github.com/canavero/exchange-service) |
| **Bottlenecks** | 20 % | **6** implementados e medidos: cache Redis, circuit breaker + retry, rate limiting, observabilidade (Prometheus + Grafana), Trivy no CI, HPA; **2 em destaque por integrante** | [Bottlenecks](projeto/bottlenecks.md) · dashboard no Grafana · vídeo |
| **AWS** | 5 % | conta do grupo com SSO, AWS CLI, roles IAM do cluster e dos nós, VPC pelo CloudFormation com o template do enunciado | [AWS e EKS](projeto/eks.md) · [Runbook](projeto/runbook.md) |
| **EKS** | 10 % | deploy real (15/11/2026): cluster `eks-store`, imagens no ECR, ELB público, Secrets/ConfigMaps, probes, HPA; smoke test **14/14** pelo ELB; ambiente reduzido ao mínimo e destruído | [AWS e EKS](projeto/eks.md) · [evidências](https://github.com/EuMiguelll/Projeto-PMA/tree/main/docs/evidencias) |
| **CI/CD** (GitHub Actions) | 10 % | pipeline por serviço (build + testes → imagem multi-arch + Trivy → deploy no EKS por OIDC), E2E da plataforma (compose + smoke test) e publicação das docs | [CI/CD](projeto/cicd.md) · execuções verdes no GitHub Actions |
| **Load Testing** | 15 % | busybox do enunciado (HPA do gateway 1 → 10 no EKS), k6 pelo ELB (2.215 req/s, 0 % de erro em `/info`), **vídeo** do teste com o HPA | [Teste de carga](projeto/load-testing.md) |
| **PaaS, custos e SLA** | 10 % | preços da AWS Price List, cenários A0/A/C, otimizações aplicadas (−38 %/h), custo real do deploy, PaaS usados, SLA composto, SLO/SLI | [Custos, PaaS e SLA](projeto/custos.md) |
| **MkDocs** | 10 % | este site (Material for MkDocs, GitHub Pages), com diagramas Mermaid, código incluído dos submódulos e uso de IA documentado | [Uso de IA](uso-de-ia.md) |

## Entrega individual (página *Presentation*)

| Pedido | Onde |
|--------|------|
| Nome do aluno e grupo | [Home](index.md) |
| Documentação e código das atividades | [Atividades](atividades.md) |
| Documentação do projeto | seção *Projeto* deste site |
| Código do projeto | [`Projeto-PMA`](https://github.com/EuMiguelll/Projeto-PMA) com os 7 submódulos em `api/` |
| Links de todos os repositórios | [Home › Repositórios](index.md#repositorios) |
| Destaques dos bottlenecks (mínimo de 2 por integrante) | [Bottlenecks › Destaques por integrante](projeto/bottlenecks.md#destaques-por-integrante) |
| Apresentação | [Apresentação e vídeo](projeto/apresentacao.md#slides) |
| Vídeo de apresentação (1–2 min) | [Apresentação e vídeo](projeto/apresentacao.md#videos) |

## Custo de AWS

Usamos o mínimo de AWS: só uma conta e uma região, e cada recurso com o teardown já planejado.
O deploy real ficou ligado ≈ 5 h e custou **≈ US$ 1,24** (pelos preços oficiais; o Cost Explorer confirma a partir de 17/11), e foi todo destruído em 16/11 às 02:30 UTC. As otimizações
derrubaram o custo por hora em 38 % (Spot, 1 NAT, sem RDS, ECR com lifecycle), e o vídeo do HPA
foi gravado num Kubernetes local (kind) com os mesmos manifests, sem gastar AWS. Detalhes em
[Custos](projeto/custos.md#custo-real-do-deploy-de-15112026).
