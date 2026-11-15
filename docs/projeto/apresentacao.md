# Apresentação e vídeo

## Vídeos

| Vídeo | Conteúdo | Link |
|-------|----------|------|
| Apresentação (1–2 min) | roteiro abaixo | _a gravar_ |
| Teste de carga + HPA | roteiro em [Teste de carga](load-testing.md) | _a gravar_ |

## Roteiro do vídeo (≈ 1 min 45 s)

| Tempo | Tela | Fala (sugestão) |
|------:|------|-----------------|
| 0:00–0:10 | slide 1 (título) | "Sou o Enzo Canavero e este é o projeto final de Plataformas: a API Store, quatro microsserviços Spring Boot implantados no Amazon EKS." |
| 0:10–0:30 | slide 2 (arquitetura) | "O cliente só fala com o **gateway**, que valida o JWT chamando o **auth** e repassa o `id-account`. O **account** guarda usuários no Postgres e o **exchange** busca cotações na AwesomeAPI. Redis serve de cache e de rate limiter." |
| 0:30–0:55 | terminal | rodar `./scripts/smoke-test.sh http://<elb>` → "registro, login com cookie JWT, conta e câmbio pelo gateway; um header `id-account` forjado é descartado." |
| 0:55–1:15 | Grafana *Store — Bottlenecks* | "Implementei seis bottlenecks, pelo menos um por serviço: rate limiting no gateway, circuit breaker no auth, cache Redis no account, cache + retry + circuit breaker no exchange, além de observabilidade e scan de vulnerabilidades no CI. Aqui o 429 do rate limit e o hit/miss do cache." |
| 1:15–1:30 | `kubectl get hpa,pods` com o busybox rodando | "Com carga, o HPA escala o gateway de 1 para várias réplicas." |
| 1:30–1:45 | slides 6–7 (custos e conclusão) | "O ambiente custa cerca de 32 centavos de dólar por hora; o pipeline do GitHub Actions testa, publica no Docker Hub e faz o deploy no EKS. Obrigado!" |

Antes de gravar: `aws/eks-create.sh` + `k8s/deploy.sh` (Runbook passos 3–6), um registro/login
prévio para o cache ter dados, Grafana aberto (`kubectl port-forward` ou o compose local) e
**destruir o cluster logo depois** (`aws/eks-teardown.sh`).

## Slides

Os slides estão em [`presentation/slides.md`](https://github.com/canavero/platform/blob/main/presentation/slides.md)
(formato [Marp](https://marp.app/): `npx @marp-team/marp-cli presentation/slides.md --pdf`, ou a
extensão *Marp for VS Code*).

| # | Slide | Conteúdo |
|--:|-------|----------|
| 1 | Introdução | título, nome, disciplina, objetivo (microsserviços em nuvem com escala automática) |
| 2 | Arquitetura | diagrama gateway → auth/account/exchange, Postgres, Redis, AwesomeAPI; padrão interface + serviço |
| 3 | Plataforma | EKS (VPC 2 AZs, node group, ELB), CI/CD (Actions → Docker Hub → EKS), observabilidade |
| 4 | Demonstração | smoke test, Grafana, HPA escalando (vídeo) |
| 5 | Desafios e bottlenecks | 6 bottlenecks com números medidos; problemas encontrados (`REDIS_PORT`, JVM × HPA, bash 3.2) |
| 6 | Custos e SLA | US$ 0,32/h (≈ US$ 237/mês), PaaS usados, disponibilidade composta 99,43 % → 99,88 % |
| 7 | Conclusão e próximos passos | RDS Multi-AZ, ECR, Ingress ALB + TLS, KEDA, Spot/Graviton |
