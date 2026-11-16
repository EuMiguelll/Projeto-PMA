# Uso de IA

O professor liberou o uso completo de IA neste projeto. **Todo o código, os scripts e esta
documentação foram gerados com o [Claude Code](https://claude.com/claude-code)** (agente de
programação da Anthropic, modelo Claude Opus), a partir de um único pedido com o escopo da
entrega e as regras de trabalho.

## Como foi usado

| Etapa | O que a IA fez | Como foi verificado |
|-------|----------------|---------------------|
| Leitura do enunciado | leu as páginas do projeto, de bottlenecks, os hands-on e o template de documentação | conferência das versões e convenções (Spring Boot 4.1.1, Spring Cloud 2025.1.3, nomes e endpoints) |
| Código dos 7 módulos | escreveu interfaces, serviços, testes, `Dockerfile` e manifests | `./mvnw` com testes em cada módulo; imagens construídas |
| Integração | `compose.yaml`, smoke test, Prometheus/Grafana | smoke test 14/14 no compose e no kind; bottlenecks forçados ao vivo (Redis, circuitos, 429) |
| Kubernetes / AWS | manifests, `deploy.sh`, scripts de EKS/RDS/teardown, Runbook | `kubeconform`, `shellcheck`, deploy em kind e **deploy real no EKS** (conta do grupo, 15/11/2026): smoke test pelo ELB e HPA 1 → 10 |
| CI/CD | workflows do GitHub Actions; stub da AwesomeAPI para o E2E | `actionlint`; execuções verdes no GitHub Actions e E2E reproduzido localmente (14/14) |
| Custos | consultou a AWS Price List e montou os cenários | valores conferidos nos arquivos oficiais de preço |
| Documentação | este site, roteiro do vídeo, checklist da rubrica e slides | `mkdocs build --strict` |
| Vídeos e slides | gravou os terminais (VHS) e o Grafana (Playwright), desenhou os slides e montou os vídeos (`ffmpeg`) no tempo do roteiro | gravações reais: smoke test contra o ELB do EKS, bottlenecks e Grafana no compose, HPA num cluster kind |

Regras dadas ao agente e seguidas: não criar recursos pagos na AWS, não publicar no GitHub sem
confirmar a conta, e poupar o computador (builds um de cada vez, checando carga e memória
antes de cada build pesado).

## Erros que a própria verificação pegou

A IA errou e só percebeu porque tudo foi executado, não apenas escrito:

- o smoke test mandava JSON quebrado por causa da *brace expansion* do bash 3.2 do macOS;
- uma checagem de segurança passava por engano (`null == null`) e foi reescrita;
- no Kubernetes, a variável `REDIS_PORT=tcp://…` injetada pelo Service `redis` derrubava três
  serviços — invisível no Docker Compose, só apareceu no teste em kind;
- uma variável de zsh (`$img:latest`) virou `atest` por causa do modificador `:l`;
- no EKS, a AwesomeAPI devolveu `429 QuotaExceeded` para os IPs dos NAT Gateways (do Mac, 200):
  só o deploy real mostrou que o exchange precisa de API key na nuvem.

## Responsabilidade do grupo

Usar IA não tira a responsabilidade de entender e defender o projeto. Antes da entrega, o grupo
deve:

- [ ] ler o código de cada serviço e saber explicar o fluxo JWT (login → cookie → `/auth/solve` → `id-account`);
- [ ] saber justificar cada bottleneck e os números medidos;
- [ ] reler o [AWS Runbook](projeto/runbook.md) e as evidências do deploy real, e gravar os vídeos;
- [ ] revisar os custos no AWS Pricing Calculator e colar o link da estimativa;
- [ ] completar as [atividades](atividades.md) feitas em aula que não estão aqui.
