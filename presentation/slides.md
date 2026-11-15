---
marp: true
theme: default
paginate: true
title: Projeto Store — Plataformas 2026.2
author: Enzo Canavero
---

# Projeto Store

### Microsserviços Spring Boot no Amazon EKS

Enzo Canavero · Plataformas · Insper 2026.2 · individual

Objetivo: API de contas e câmbio com autenticação, resiliência e **escala automática** na nuvem.

---

## Arquitetura

```text
Internet ──► gateway (Spring Cloud Gateway: JWT + rate limit)
                ├─► auth      (JJWT, circuit breaker) ──Feign──► account
                ├─► account   (JPA + Flyway, cache) ──► PostgreSQL
                └─► exchange  (RestClient, cache + retry + CB) ──► AwesomeAPI
             Redis: cache + rate limiter     Prometheus ► Grafana
```

- Padrão da disciplina: **interface** (`@FeignClient` + `record`) + **serviço**, 7 repositórios
- Só o gateway é exposto; ele remove `id-account` do cliente e o recoloca a partir do JWT

---

## Plataforma

- **EKS** em us-east-2: VPC do template (2 AZs, subnets privadas), 2 × `t3.medium`, ELB
- **Kubernetes**: Deployment + probes, Service, ConfigMap/Secret, **HPA** (CPU 50 %)
- **CI/CD** (GitHub Actions): testes → imagem multi-arch no Docker Hub → Trivy → `kubectl set image :sha`
- **Local**: `docker compose up` (Postgres, Redis, Prometheus, Grafana) + smoke test 15/15
- Mesmos manifests validados num cluster **kind** antes do EKS

---

## Demonstração

1. `./scripts/smoke-test.sh http://<elb>` — registro, login (cookie JWT), conta, câmbio
2. Grafana *Store — Bottlenecks* — req/s, latência, 429, circuitos, cache hit/miss
3. `load-test/busybox.sh` + `kubectl get hpa,pods` — gateway **1 → 4 réplicas** (kind)

*(vídeo)*

---

## Bottlenecks e desafios

| Bottleneck | Medido |
|------------|--------|
| Cache Redis (account, exchange) | 2ª leitura sem ir ao banco/API |
| Circuit breaker + retry | 503 em ~5 ms com o circuito aberto (vs 1,2 s) |
| Rate limiting (gateway) | 150 de 300 requisições → 429 |
| Observabilidade, Trivy, HPA | 4 targets UP, scan no CI, 1 → 4 pods |

Desafios: `REDIS_PORT=tcp://…` injetado pelo k8s, pico de CPU da JVM disparando o HPA,
brace expansion do bash 3.2 no smoke test

---

## Custos e SLA (us-east-2)

- **≈ US$ 0,32/h — US$ 237/mês**: EKS 73 · NAT 67 · EC2 61 · LB 18 · IPv4 15 · EBS 3
- Gravação do projeto (~3 h): **≈ US$ 1**; otimizado (1 NAT, Graviton): US$ 188/mês
- PaaS: EKS, ELB, RDS, CloudFormation, GitHub Actions/Pages
- Disponibilidade composta: **99,43 %** (RDS Single-AZ) → **99,88 %** (Multi-AZ)
- SLO 99,5 % · SLA 99,0 %

---

## Conclusão e próximos passos

- Plataforma completa: código, testes, imagens, k8s, CI/CD, docs e custos
- Próximos passos: RDS Multi-AZ, ECR, Ingress ALB + TLS, KEDA (escala por req/s),
  nós Spot/Graviton, Redis gerenciado (ElastiCache)

**Obrigado!** · docs: `https://canavero.github.io/platform/`
