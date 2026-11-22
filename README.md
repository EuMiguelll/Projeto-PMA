# Projeto Store — Plataformas 2026.2

Enzo Canavero e Miguel Damásio (dupla). Microsserviços — gateway, auth e account em Spring Boot,
exchange em Python/FastAPI — com Docker, Kubernetes/EKS, GitHub Actions, bottlenecks, teste de
carga e análise de custos.

**Documentação:** https://eumiguelll.github.io/Projeto-PMA/ (fonte em `docs/`).

> **Exchange: usamos o serviço do BACEN da disciplina.** O Exchange é o serviço em Python/FastAPI
> da página [API de Câmbio: serviço do BACEN](https://insper.github.io/platform/2026.2/exercises/exchange/bacen/),
> sobre a PTAX do Banco Central (pública, sem chave), em [`api/exchange-py/`](api/exchange-py), com
> o nosso Dockerfile (python:3.12-slim + uv), testes, métricas e algumas melhorias que mantêm o
> contrato. Por quê: o enunciado pede o Exchange em Python, e as APIs de câmbio gratuitas recusam
> IPs da AWS (a AwesomeAPI nos devolveu `429` no EKS); a PTAX é pública e o professor indicou
> consultá-la direto. O `exchange-service` em Java (submódulo) ficou como versão anterior, fora
> do gateway. Detalhes: [Exchange](https://eumiguelll.github.io/Projeto-PMA/projeto/exchange/).

```bash
git clone --recurse-submodules https://github.com/EuMiguelll/Projeto-PMA.git && cd Projeto-PMA
./scripts/build.sh                 # 7 módulos Java (mvnw) + exchange-py (uv + pytest), um por vez
docker compose up -d --build       # Postgres, Redis, 4 serviços, Prometheus, Grafana
./scripts/smoke-test.sh            # registro → login → conta → câmbio pelo gateway (21 verificações)
```

AWS: [AWS_RUNBOOK.md](AWS_RUNBOOK.md) · Publicação no GitHub: `./publish.sh`
