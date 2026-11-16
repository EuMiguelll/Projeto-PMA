# CI/CD — GitHub Actions

O enunciado aceita Jenkins **ou** GitHub Actions; usamos **GitHub Actions** (zero infraestrutura,
gratuito para repositórios públicos), seguindo o apêndice *GitHub Actions* da disciplina e as
etapas pedidas no exercício Jenkins: **SCM → Dependencies → Build → Push da imagem → Deploy to K8s**.
O registry é o **Amazon ECR** da conta do grupo (o mesmo usado no deploy real) ou o Docker Hub.

```mermaid
flowchart LR
    push([push em main]) --> build
    subgraph wf [".github/workflows/ci.yml (cada serviço)"]
        build["Build & Test<br/>checkout + interfaces<br/>mvnw verify"] --> image["Imagem: ECR ou Docker Hub<br/>buildx amd64+arm64<br/>tags :latest e :sha<br/>Trivy"]
        image --> deploy["Deploy EKS<br/>kubectl set image :sha<br/>rollout status"]
    end
    pr([pull request]) --> build
    image -. "só se vars.AWS_ECR ou vars.DOCKERHUB_USERNAME" .- image
    deploy -. "só se vars.EKS_CLUSTER" .- deploy
```

| Job | Quando roda | O que faz |
|-----|-------------|-----------|
| **Build & Test** | todo push e PR | checkout do serviço **e dos módulos de interface** (repositórios irmãos, `mvn install`), `./mvnw verify` (testes + jar), artefato `jar` |
| **Imagem** | push (não PR) e variável `AWS_ECR=true` ou `DOCKERHUB_USERNAME` | credenciais AWS por **OIDC** (sem chave fixa), login no ECR (ou Docker Hub), QEMU + Buildx, imagem `linux/amd64,linux/arm64`, tags `:latest` e `:<sha>`, **Trivy** (HIGH/CRITICAL) |
| **Deploy EKS** | push em `main` e variável `EKS_CLUSTER` definida | mesma role OIDC, `aws eks update-kubeconfig`, `kubectl set image deployment/<svc> <svc>=<imagem>:<sha>`, `kubectl rollout status` |

Sem as variáveis, os jobs de imagem e deploy ficam **skipped** (não falham) — o pipeline já
funciona antes da AWS existir. Os módulos de interface (`account`, `auth`, `exchange`) têm um
workflow só de build; o repositório principal tem o **E2E** (compose + smoke test com os
submódulos) e o **docs** (MkDocs → GitHub Pages).

??? example "api/auth-service/.github/workflows/ci.yml"

    ```yaml
    --8<-- "api/auth-service/.github/workflows/ci.yml"
    ```

??? example ".github/workflows/e2e.yml (repositório principal)"

    ```yaml
    --8<-- ".github/workflows/e2e.yml"
    ```

## Configuração (uma vez por repositório de serviço)

| Tipo | Nome | Valor |
|------|------|-------|
| variable | `AWS_ECR` | `true` (imagem no ECR) |
| secret | `AWS_ROLE_ARN` | role `github-actions-store` (OIDC; Runbook, passo 7) |
| variable | `EKS_CLUSTER` | `eks-store` |
| variable | `AWS_REGION` | `us-east-2` (padrão) |
| variable / secret | `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` | alternativa ao ECR |
| secret | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | alternativa ao OIDC (não recomendada) |

A role `github-actions-store` só aceita tokens dos repositórios `*-service` na branch `main`,
tem `AmazonEC2ContainerRegistryPowerUser` + `eks:DescribeCluster` no IAM e a access policy
`AmazonEKSEditPolicy` restrita ao namespace `default` — suficiente para publicar imagens e
atualizar Deployments, sem poder administrar o cluster. Nenhuma chave de longa duração existe,
e o ID da conta não vai para arquivos nem para os logs públicos (`mask-aws-account-id: true`).

## Execuções no GitHub Actions

Os workflows rodam no GitHub a cada push (15/11/2026, 23:01 UTC):

| Repositório | Workflow | Build & Test | Imagem + Trivy | Deploy EKS |
|-------------|----------|:------------:|:--------------:|:----------:|
| [`gateway-service`](https://github.com/canavero/gateway-service/actions) | CI/CD | ✅ | ⏭️ | ⏭️ |
| [`auth-service`](https://github.com/canavero/auth-service/actions) | CI/CD | ✅ | ⏭️ | ⏭️ |
| [`account-service`](https://github.com/canavero/account-service/actions) | CI/CD | ✅ | ⏭️ | ⏭️ |
| [`exchange-service`](https://github.com/canavero/exchange-service/actions) | CI/CD | ✅ | ⏭️ | ⏭️ |
| [`auth`](https://github.com/canavero/auth/actions), [`account`](https://github.com/canavero/account/actions), [`exchange`](https://github.com/canavero/exchange/actions) | CI (interfaces) | ✅ | — | — |
| [`platform`](https://github.com/canavero/platform/actions) | E2E e docs | ✅ | — | — |

⏭️ = *skipped* de propósito: os jobs de imagem e deploy só ligam com as variáveis `AWS_ECR`/`EKS_CLUSTER`
e a role OIDC. Para o deploy real, os mesmos passos rodaram à mão, com os mesmos comandos
(`push-images.sh` → ECR, `deploy.sh`, `kubectl set image`), como mostram as
[evidências](eks.md#deploy-real-no-eks-15112026). A role OIDC não foi criada: deixaria o ARN da
conta do grupo no GitHub e um cluster ligado esperando deploys, o que contraria a meta de usar o
mínimo de AWS.

### E2E hermético

O E2E sobe a plataforma inteira com `docker compose` e roda o smoke test pelo gateway (14
verificações). Os runners do GitHub recebem `429` da AwesomeAPI quando chamam sem API key, e o
teste ficava vermelho por um motivo externo ao código. Por isso, no CI o `exchange` fala com um
**stub** da AwesomeAPI (nginx com respostas fixas, `setup/provider-stub/default.conf`), que
devolve a cotação de `USD-BRL` e `404` para pares inexistentes, como a API real. O teste fica
determinístico e não depende de quota de terceiros. O provedor real foi validado no EKS (smoke
test 14/14 pelo ELB, com a API key no Secret `exchange-secrets`).

```bash
EXCHANGE_PROVIDER_URL=http://provider-stub docker compose --profile e2e up -d --build \
  db redis provider-stub account auth exchange gateway
./scripts/smoke-test.sh   # 14/14
```

## Boas práticas aplicadas

- `permissions: contents: read` (menor privilégio do `GITHUB_TOKEN`); segredos só em *secrets*.
- Cache do Maven (`actions/setup-java` com `cache: maven`).
- Imagem identificada pelo **SHA do commit** — rastreável e imutável; o deploy usa o SHA, não `latest`.
- Deploy com `rollout status`: o job falha se os pods novos não ficarem prontos (readiness probe),
  e o Kubernetes mantém os pods antigos atendendo (rolling update).
- Lint dos workflows com `actionlint` e dos scripts com `shellcheck` antes do commit.
