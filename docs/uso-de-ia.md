# Uso de IA

A página do projeto permite usar IA na implementação e pede que o grupo documente o que foi
feito com ela e o que foi feito pelos integrantes. Neste projeto, a divisão foi esta:

- **Nós dois (Miguel Damásio e Enzo Canavero)** idealizamos o projeto, definimos a arquitetura,
  dividimos as tarefas, coordenamos o trabalho e atuamos como **arquitetos do sistema e gestores
  dos agentes de IA**: decidimos o que construir, em que ordem, com quais regras, e revisamos e
  validamos cada entrega antes de seguir.
- **A IA** ([Claude Code](https://claude.com/claude-code), agente de programação da Anthropic)
  fez o **trabalho bruto**: escreveu o código dos 7 módulos, os testes, os `Dockerfile`, os
  manifests, os scripts, os rascunhos desta documentação e a montagem dos vídeos.

## O que foi nosso

| Frente | Decisões e trabalho da dupla |
|--------|------------------------------|
| **Ideação e escopo** | API Store com os 4 microsserviços pedidos (gateway, auth, account, exchange), padrão interface + serviço da disciplina, repositório principal com submódulos |
| **Arquitetura** | gateway como única porta de entrada; JWT validado no gateway (o cliente nunca manda o `id-account`); Postgres para contas; Redis compartilhado para cache e rate limiting; circuit breaker nas chamadas síncronas; HPA por serviço |
| **Divisão de tarefas** | cada integrante responde por 2 bottlenecks: **Miguel** por rate limiting e observabilidade, **Enzo** por cache e circuit breaker ([destaques](projeto/bottlenecks.md#destaques-por-integrante)). **Enzo** conduziu o deploy real no EKS e a otimização de custos; **Miguel** conduziu a entrega final: E2E do CI, vídeos, apresentação, checklist da rubrica, revisão da documentação e a troca do Exchange para o serviço Python do BACEN |
| **Gestão dos agentes** | escrevemos os pedidos e as regras de trabalho, aprovamos cada passo que gastava AWS ou publicava algo, e checamos as saídas reais (testes, smoke test, HPA, custos) antes de aceitar |
| **Custos e segurança** | decidimos usar o mínimo de AWS (nós Spot, 1 NAT, Postgres no cluster, teardown automático, vídeo do HPA gravado localmente) e as regras para nada da conta ir ao GitHub |
| **Revisão** | conferimos o código, a documentação, os números de custo e os vídeos, e respondemos pelo projeto inteiro na prova oral |

## O que a IA fez e como verificamos

| Etapa | O que a IA fez | Como verificamos |
|-------|----------------|------------------|
| Leitura do enunciado | resumiu as páginas do projeto, de bottlenecks, os hands-on e o template de documentação | conferência das versões e convenções (Spring Boot 4.1.1, Spring Cloud 2025.1.3, nomes e endpoints) |
| Código dos 7 módulos | escreveu interfaces, serviços, testes, `Dockerfile` e manifests | `./mvnw` com testes em cada módulo; imagens construídas |
| Integração | `compose.yaml`, smoke test, Prometheus/Grafana | smoke test 14/14 no compose e no kind; bottlenecks forçados ao vivo (Redis, circuitos, 429) |
| Kubernetes / AWS | manifests, `deploy.sh`, scripts de EKS/RDS/teardown, Runbook | `kubeconform`, `shellcheck`, deploy em kind e **deploy real no EKS** (conta do grupo, 15/11/2026): smoke test pelo ELB e HPA 1 → 10 |
| CI/CD | workflows do GitHub Actions; stub do provedor de câmbio para o E2E | `actionlint`; execuções verdes no GitHub Actions e E2E reproduzido localmente (14/14) |
| Custos | consultou a AWS Price List e montou os cenários | valores conferidos nos arquivos oficiais de preço e no AWS Pricing Calculator |
| Exchange em Python (22/11) | adaptou o serviço FastAPI da página do BACEN (`api/exchange-py`), escreveu os testes com a PTAX simulada, o `Dockerfile`, o manifest, o workflow e a integração no gateway/compose | 37 testes + 2 contra a PTAX real; mutações no código (fórmula invertida, regex sem âncora, sem lock…) derrubam a suíte; smoke test 18/18 pelo gateway com a PTAX real; comparação medida com o serviço original |
| Documentação | rascunhos deste site, do roteiro do vídeo, do checklist da rubrica e dos slides | revisão nossa e `mkdocs build --strict` |
| Vídeos e slides | gravou os terminais (VHS) e o Grafana (Playwright), desenhou os slides e montou os vídeos (`ffmpeg`) no tempo do roteiro | gravações reais: smoke test contra o ELB do EKS, bottlenecks e Grafana no compose, HPA num cluster kind |

Regras que demos aos agentes: não criar recursos pagos na AWS sem o nosso aval e sem teardown
planejado, nunca versionar nada que identifique a conta (ID, ARNs, chaves), não publicar no
GitHub sem confirmar a conta, e poupar o computador (builds um de cada vez).

## Erros que a verificação pegou

A IA errou, e os erros só apareceram porque mandamos executar tudo, não apenas escrever:

- o smoke test mandava JSON quebrado por causa da *brace expansion* do bash 3.2 do macOS;
- uma checagem de segurança passava por engano (`null == null`) e foi reescrita;
- no Kubernetes, a variável `REDIS_PORT=tcp://…` injetada pelo Service `redis` derrubava três
  serviços — invisível no Docker Compose, só apareceu no teste em kind;
- uma variável de zsh (`$img:latest`) virou `atest` por causa do modificador `:l`;
- no EKS, a AwesomeAPI devolveu `429 QuotaExceeded` para os IPs dos NAT Gateways (do Mac, 200):
  só o deploy real mostrou que o exchange precisa de API key na nuvem;
- o E2E do GitHub Actions falhava pelo mesmo `429`, por um motivo externo ao código: trocamos a
  API real por um stub no CI;
- com o aviso do professor (16/11) de que APIs gratuitas recusam IPs da AWS, trocamos a
  AwesomeAPI pelo PTAX do BACEN, que dispensa chave (o stub do CI passou a imitar o PTAX);
- o enunciado pede o Exchange em Python, e a versão Java não seguia isso: em 22/11 ele passou a
  ser o serviço FastAPI do BACEN da disciplina. Na adaptação, um teste mostrou que o `pattern` do
  Pydantic procura o padrão em qualquer parte do texto (`USDT` passava por `[A-Za-z]{3}`) e o
  regex ganhou `^…$`;
- a primeira simulação de "PTAX lenta" usava um IP que falhava na hora, e a evidência não mostrava
  o que dizia; trocamos por um servidor que demora 10 s de verdade e **medimos** o serviço
  original lado a lado (fila de 3 a 30 s, e a exceção interna no corpo do 502) em vez de supor.

## Responsabilidade

Usar IA não tira de nós a responsabilidade de entender e defender o projeto. Os dois sabem
explicar o fluxo do JWT (login → cookie → `/auth/solve` → `id-account`), justificar cada
bottleneck com os números medidos, reproduzir o deploy pelo [Runbook](projeto/runbook.md) e
defender as escolhas de custo.
