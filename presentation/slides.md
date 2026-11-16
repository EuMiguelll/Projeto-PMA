---
marp: true
theme: default
paginate: true
title: Projeto Store — Plataformas 2026.2
author: Enzo Canavero e Miguel Damásio
---

# Projeto Store

### Microsserviços Spring Boot no Amazon EKS

Enzo Canavero e Miguel Damásio · Plataformas · Insper 2026.2

Objetivo: API de contas e câmbio com autenticação, resiliência e **escala automática** na nuvem.

---

## Arquitetura

```text
Internet ──► gateway (Spring Cloud Gateway: JWT + rate limit)
                ├─► auth      (JJWT, circuit breaker) ──Feign──► account
                ├─► account   (JPA + Flyway, cache) ──► PostgreSQL
                └─► exchange  (RestClient, cache + retry + CB) ──► BACEN (PTAX)
             Redis: cache + rate limiter     Prometheus ► Grafana
```

- Padrão da disciplina: **interface** (`@FeignClient` + `record`) + **serviço**, 7 repositórios
- Só o gateway é exposto; ele remove `id-account` do cliente e o recoloca a partir do JWT

---

## Plataforma

- **EKS** em us-east-2 (deploy real): VPC do template (2 AZs, subnets privadas, 1 NAT),
  2 × `t3.medium` **Spot**, Postgres no cluster (RDS validado no 1º deploy), ECR com lifecycle, 1 ELB
- **Kubernetes**: Deployment + probes, Service, ConfigMap/Secret, **HPA** (CPU 50 %)
- **CI/CD** (GitHub Actions): testes → imagem multi-arch no ECR (OIDC, sem chave) → Trivy → `kubectl set image :sha`
- **Local**: `docker compose up` (Postgres, Redis, Prometheus, Grafana) + smoke test 14/14
- Mesmos manifests validados num cluster **kind** antes do EKS

---

## Demonstração

1. `./scripts/smoke-test.sh http://<elb>` — registro, login (cookie JWT), conta, câmbio
2. Grafana *Store — Bottlenecks* — req/s, latência, 429, circuitos, cache hit/miss
3. `load-test/busybox.sh` + `kubectl get hpa,pods` — gateway **1 → 10 réplicas em ~80 s** (EKS)

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

- 1º deploy: US$ 0,34/h (US$ 251/mês) → **otimizado: ≈ US$ 0,21/h (US$ 155/mês, −38 %)**
- Spot −0,062/h · 1 NAT −0,05/h · sem RDS −0,019/h · ECR com lifecycle · teardown automático 3 h
- Agora: EKS 73 · NAT 34 · LB 18 · EC2 Spot 15 · IPv4 11 · EBS+ECR 3 · deploy real ≈ **US$ 1,24**, destruído em 16/11
- PaaS: EKS, ELB, RDS, ECR, CloudFormation, GitHub Actions/Pages
- Disponibilidade composta (produção): **99,43 %** (RDS Single-AZ) → **99,88 %** (Multi-AZ)
- SLO 99,5 % · SLA 99,0 %

---

## Conclusão e próximos passos

- Plataforma completa: código, testes, imagens, k8s, CI/CD, docs e custos
- Próximos passos: RDS Multi-AZ, ECR, Ingress ALB + TLS, KEDA (escala por req/s),
  nós Spot/Graviton, Redis gerenciado (ElastiCache)

**Obrigado!** · docs: `https://eumiguelll.github.io/Projeto-PMA/`
