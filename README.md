# Projeto Store — Plataformas 2026.2

Enzo Canavero (individual). Microsserviços Spring Boot (gateway, auth, account, exchange) com
Docker, Kubernetes/EKS, GitHub Actions, bottlenecks, teste de carga e análise de custos.

**Documentação:** https://canavero.github.io/platform/ (fonte em `docs/`).

```bash
git clone --recurse-submodules https://github.com/canavero/platform.git && cd platform
./scripts/build.sh                 # compila os 7 módulos (um por vez)
docker compose up -d --build       # Postgres, Redis, 4 serviços, Prometheus, Grafana
./scripts/smoke-test.sh            # registro → login → conta → câmbio pelo gateway
```

AWS: [AWS_RUNBOOK.md](AWS_RUNBOOK.md) · Publicação no GitHub: `./publish.sh`
