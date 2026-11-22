# AWS Runbook — do zero ao EKS (e de volta a zero)

Roteiro executável para subir a plataforma **Store** na AWS, gravar o teste de carga e
**desligar tudo**. Os scripts seguem a ordem do enunciado (páginas *AWS* e *EKS*):
VPC via CloudFormation (template `amazon-eks-vpc-private-subnets.yaml`) → role do cluster →
cluster EKS → role do node group → node group só nas subnets privadas → kubeconfig. Tudo no
tamanho mínimo que ainda aguenta o teste de carga (nós Spot, 1 NAT, Postgres no cluster).

!!! danger "Isto custa dinheiro"
    Com 2 nós `t3.medium` **Spot**, 1 NAT Gateway, 1 Load Balancer e o Postgres no cluster, o
    ambiente custa **≈ US$ 0,21/hora (≈ US$ 5/dia)** enquanto existir, mesmo parado (o primeiro
    deploy, com 2 NAT, nós on-demand e RDS, custava US$ 0,34/h). Planeje uma sessão de ~2–3 h
    (< US$ 1), agende o teardown de segurança (3 h) e rode o **passo 9 (teardown)** no final.
    Detalhes na análise de custos (`docs/projeto/custos.md`).

| Passo | O quê | Tempo | Custo |
|------:|-------|------:|-------|
| 0 | Ferramentas | 5 min | — |
| 1 | Credenciais (SSO ou usuário IAM), alerta de orçamento | 10 min | — |
| 2 | Imagens no Amazon ECR (`./scripts/push-images.sh`) | 5 min | centavos/mês |
| 3 | `./aws/eks-create.sh` (VPC + EKS + nós + metrics-server) | 20 min | começa a cobrar |
| 4 | (opcional) `./aws/rds-create.sh` (PostgreSQL no RDS; o padrão é o Postgres no cluster) | 10 min | + US$ 0,02/h |
| 5 | `./k8s/deploy.sh` | 5 min | + Load Balancer |
| 6 | Smoke test no ELB | 1 min | — |
| 7 | CI/CD com deploy no EKS | 10 min | — |
| 8 | Teste de carga + vídeo do HPA | 15 min | — |
| 9 | `./aws/eks-teardown.sh` | 15 min | para de cobrar |

---

## 0. Ferramentas

```bash
brew install awscli kubectl        # macOS (AWS CLI v2)
aws --version && kubectl version --client
docker --version                   # Docker Desktop ligado (para build/push das imagens)
```

## 1. Conta, usuário IAM e credenciais

!!! tip "Conta do grupo no Insper (IAM Identity Center / SSO) — o caminho usado"
    A conta do grupo já vem com o papel `AdministratorAccess` via SSO; não crie usuário nem access key:

    ```bash
    aws configure sso          # uma vez: start URL do Insper, região do SSO, conta do grupo, us-east-2
    aws sso login              # quando a sessão expirar
    aws sts get-caller-identity
    ```

    **Nunca** coloque ID da conta, ARNs, chaves ou senhas em arquivos versionados: os scripts
    descobrem a conta em tempo de execução (`aws sts get-caller-identity`).

Conta própria, seguindo a página *AWS* do enunciado (nunca use o usuário root no dia a dia):

1. Console AWS → **IAM → Users → Create user** (ex.: `enzo-admin`), com acesso ao console.
2. **Permissions → Attach policies directly → `AdministratorAccess`** (projeto acadêmico; em
   produção, restrinja).
3. Faça login com esse usuário e crie uma **Access key** (IAM → Users → *usuário* →
   *Security credentials* → *Create access key* → *Command Line Interface (CLI)*).
4. Configure a CLI na região do projeto (**us-east-2**, Ohio — a mesma do enunciado):

```bash
aws configure            # Access key, Secret, region: us-east-2, output: json
aws configure list
aws sts get-caller-identity
```

**Alerta de orçamento (recomendado)** — avisa por e-mail se o gasto do mês passar de US$ 20:

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws budgets create-budget --account-id "$ACCOUNT" \
  --budget '{"BudgetName":"plataformas","BudgetLimit":{"Amount":"20","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
  --notifications-with-subscribers '[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":50},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"SEU-EMAIL@exemplo.com"}]}]'
```

!!! tip "AWS Academy / Learner Lab"
    Se a conta não permite criar roles IAM, use a `LabRole` existente:
    `CLUSTER_ROLE_ARN=arn:aws:iam::<conta>:role/LabRole NODE_ROLE_ARN=arn:aws:iam::<conta>:role/LabRole ./aws/eks-create.sh`.

## 2. Imagens no Amazon ECR

Os nós são **x86 (t3)**, então a imagem precisa de `linux/amd64`; o script publica `amd64` +
`arm64`. O ECR da própria conta é o registry padrão: a role dos nós já tem
`AmazonEC2ContainerRegistryReadOnly` (sem `imagePullSecrets`) e não há limite de pulls.

```bash
./scripts/build.sh            # gera os target/*.jar
./scripts/push-images.sh      # cria os repositórios <serviço>-service (scan on push) e faz o push
aws ecr describe-images --repository-name gateway-service --query 'imageDetails[].imageTags'
```

Alternativa Docker Hub: `docker login && DOCKERHUB_USERNAME=<usuario> ./scripts/push-images.sh`
(e o mesmo `DOCKERHUB_USERNAME` no passo 5). Pelo CI: passo 7.

## 3. Criar VPC + cluster EKS + node group

```bash
./aws/eks-create.sh            # padrão: us-east-2, cluster eks-store, 2 x t3.medium Spot
# variáveis: AWS_REGION, CLUSTER, NODE_TYPES (padrão "t3.medium t3a.medium"), NODES
```

O script é idempotente (pode ser rodado de novo se cair no meio) e faz:

1. `aws cloudformation deploy` do template do enunciado → VPC `192.168.0.0/16`, 2 subnets
   públicas (load balancers, tag `kubernetes.io/role/elb`) e 2 privadas (pods, tag
   `kubernetes.io/role/internal-elb`) em duas AZs e **1 NAT Gateway** compartilhado (o template
   original cria 1 por AZ; o único ajuste foi esse, que economiza US$ 0,05/h);
2. role `eksClusterRole` com `AmazonEKSClusterPolicy`;
3. `aws eks create-cluster` (endpoint público, autenticação por *access entries*, upgrade
   policy `STANDARD` para nunca cair no suporte estendido, que custa US$ 0,60/h) e espera ficar `ACTIVE`;
4. role `eksNodeRole` com `AmazonEKS_CNI_Policy`, `AmazonEKSWorkerNodePolicy`,
   `AmazonEC2ContainerRegistryReadOnly` (as três do enunciado);
5. node group gerenciado **Spot** (`t3.medium` ou `t3a.medium`, mín. 1, máx. 2; ~75 % mais
   barato que on-demand) **só nas subnets privadas**;
6. `aws eks update-kubeconfig --name eks-store` + **metrics-server** (o HPA depende dele).

Conferência:

```bash
kubectl config get-contexts
kubectl get nodes -o wide          # 2 nós Ready, IPs 192.168.128.x / 192.168.192.x (privados)
kubectl top nodes                  # metrics-server ok (leva ~1 min)
```

## 4. (Opcional) Banco gerenciado — Amazon RDS

A página *EKS* do enunciado sugere **Amazon RDS ou DynamoDB**. O RDS PostgreSQL `db.t4g.micro`
(≈ US$ 0,019/h com o disco) foi usado e validado no primeiro deploy. Para dev/teste e para o
vídeo, o padrão agora é o Postgres **dentro do cluster** (`k8s/postgres.yaml`, sem custo extra e
sem persistência). Pule este passo, a menos que precise de um banco que sobreviva ao pod:

```bash
export DATABASE_PASSWORD=$(openssl rand -hex 16)   # só no shell; nunca em arquivo versionado
./aws/rds-create.sh                                # imprime o DATABASE_HOST a usar no passo 5
```

Cria `db.t4g.micro` PostgreSQL 17, 20 GB gp3, Single-AZ, **sem IP público**, nas subnets privadas,
com security group liberando a porta 5432 só para os nós do EKS.

## 5. Implantar a plataforma

```bash
./k8s/deploy.sh                                       # Postgres no cluster (padrão)
# com RDS: DATABASE_HOST=<endpoint do passo 4> ./k8s/deploy.sh  (usa o $DATABASE_PASSWORD do passo 4)
# imagens no Docker Hub: DOCKERHUB_USERNAME=<usuario> ./k8s/deploy.sh
```

O script troca o prefixo `DOCKERHUB_USER` dos manifests pelo registry do ECR da conta (descoberto
na hora), aplica `k8s/redis.yaml`, `k8s/postgres.yaml` (só sem RDS) e o
`api/<serviço>/k8s/k8s.yaml` de cada serviço (Secret, ConfigMap, Deployment, Service, HPA),
sobrescreve os segredos de desenvolvimento (JWT aleatório, senha do RDS) e espera os rollouts.
No fim imprime a URL do ELB.

```bash
kubectl get pods,svc,hpa
kubectl get svc gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

## 6. Testar

```bash
ELB=$(kubectl get svc gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
curl http://$ELB/health-check          # {"hostname":"gateway-..."}
curl http://$ELB/info
./scripts/smoke-test.sh http://$ELB    # registro, login, rotas seguras, exchange (18 verificações)

# a PTAX do BCB responde da AWS? Uma chamada de dentro de um pod, como pede a página do BACEN
kubectl run ptax --rm -i --restart=Never --image=curlimages/curl:8.17.0 -- \
  curl -s -w '\nHTTP %{http_code}\n' 'https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/Moedas?$format=json&$top=1'
```

!!! note "Cookie `Secure` em HTTP"
    O login devolve o JWT em cookie `HttpOnly; Secure; SameSite=None` (como no hands-on 3).
    `curl`/k6/smoke test enviam o cookie explicitamente; **um navegador só o reenvia por HTTPS**
    (para isso: Ingress com ALB + certificado do ACM, seção 10).

## 7. CI/CD: imagem no ECR e deploy automático no EKS

O job `image` publica no ECR (ou no Docker Hub) e o `deploy` faz
`kubectl set image deployment/<serviço> <serviço>=<imagem>:<sha>` + `kubectl rollout status`.
Sem chave fixa: o GitHub Actions troca o token **OIDC** do workflow por credenciais temporárias de
uma role que só aceita os repositórios de serviço na branch `main`.

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
aws iam create-role --role-name github-actions-store --assume-role-policy-document '{
  "Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sts:AssumeRoleWithWebIdentity",
  "Principal":{"Federated":"arn:aws:iam::'"$ACCOUNT"':oidc-provider/token.actions.githubusercontent.com"},
  "Condition":{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com"},
               "StringLike":{"token.actions.githubusercontent.com:sub":["repo:<owner>/*-service:ref:refs/heads/main",
                                                                      "repo:<main-owner>/Projeto-PMA:ref:refs/heads/main"]}}}]}'
aws iam attach-role-policy --role-name github-actions-store \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
aws iam put-role-policy --role-name github-actions-store --policy-name eks-describe \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"eks:DescribeCluster","Resource":"*"}]}'
aws eks create-access-entry --cluster-name eks-store \
  --principal-arn "arn:aws:iam::$ACCOUNT:role/github-actions-store"
aws eks associate-access-policy --cluster-name eks-store \
  --principal-arn "arn:aws:iam::$ACCOUNT:role/github-actions-store" \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy \
  --access-scope type=namespace,namespaces=default

# o exchange-py (Python) mora no repositório principal: o workflow dele lê as variáveis de lá
for r in "<owner>/account-service" "<owner>/auth-service" "<owner>/gateway-service" "<main-owner>/Projeto-PMA"; do
  gh variable set AWS_ECR -b true -R "$r"
  gh variable set EKS_CLUSTER -b eks-store -R "$r"
  gh secret set AWS_ROLE_ARN -b "arn:aws:iam::$ACCOUNT:role/github-actions-store" -R "$r"
done
```

O ARN vai como **secret** (mascarado nos logs) e o workflow usa `mask-aws-account-id: true`, então o
ID da conta não aparece nos logs públicos. Teste: um commit em `main` de qualquer serviço →
Actions: **Build & Test → Imagem → Deploy EKS**.

## 8. Teste de carga e vídeo do HPA

Ver `load-test/README.md` (página *Teste de carga* do site) — 3 terminais (HPA, pods, gerador de carga
busybox do enunciado) e a alternativa com k6.

## 9. Teardown (obrigatório)

```bash
./aws/eks-teardown.sh
```

Remove, nesta ordem: Service `LoadBalancer`/Ingress (libera o ELB) → RDS (se houver) →
node groups → cluster → stack da VPC (subnets, NAT Gateway, Elastic IP) → repositórios do ECR.
As roles IAM ficam (não custam nada). Antes de começar, o script aponta o `kubectl` para o
`eks-store` (`aws eks update-kubeconfig`), para não apagar nada de outro cluster.

**Teardown de segurança** (caso alguém esqueça o cluster ligado): agende ao terminar o deploy,
na pasta do repositório. Em **3 h** ele roda o `eks-teardown.sh`, a menos que exista `~/KEEP_EKS`
(3 h bastam para implantar, testar e gravar; cada hora a mais custa US$ 0,21).

```bash
perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV' \
  nohup caffeinate -i sh -c 'sleep 10800; [ -f ~/KEEP_EKS ] || ./aws/eks-teardown.sh' \
  > ~/eks-teardown.log 2>&1 < /dev/null & echo $! > ~/eks-teardown.pid
ps -o pid,pgid,command -g "$(cat ~/eks-teardown.pid)"    # sh, caffeinate e sleep no mesmo grupo
```

- **Manter o cluster**: `touch ~/KEEP_EKS`. **Cancelar o agendamento**:
  `kill -- -$(cat ~/eks-teardown.pid)` (o `-` mata o grupo todo; matar só o `sleep` dispararia o
  teardown na hora).
- `setsid` põe o processo numa sessão própria (sobrevive ao fechar o terminal);
  `caffeinate -i` impede o repouso por inatividade, mas **fechar a tampa na bateria suspende o
  Mac** e atrasa o relógio do `sleep`.
- As credenciais precisam valer na hora: com SSO, as do papel ficam em cache por até 12 h
  (`jq -r .Credentials.Expiration ~/.aws/cli/cache/*.json`). Depois disso só com `aws sso login`.
- Log em `~/eks-teardown.log`.

Depois confira no console, região **us-east-2**:

- [ ] EKS → Clusters: vazio
- [ ] EC2 → Instances, Load Balancers, NAT Gateways, Elastic IPs, Volumes: vazios
- [ ] RDS → Databases: vazio
- [ ] CloudFormation → Stacks: sem `eks-store-vpc`
- [ ] ECR → Repositories: vazio
- [ ] (opcional) IAM → role `github-actions-store` e o provedor OIDC do GitHub

## 10. (Opcional) Ingress com ALB e HTTPS

O padrão do projeto é o `Service` `type: LoadBalancer` do gateway (um Classic Load Balancer, sem
componentes extras). Para um **ALB** com Ingress (`k8s/ingress.yaml`) é preciso o
AWS Load Balancer Controller:

```bash
brew install eksctl helm
eksctl utils associate-iam-oidc-provider --cluster eks-store --approve
curl -sO https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json
aws iam create-policy --policy-name AWSLoadBalancerControllerIAMPolicy --policy-document file://iam_policy.json
eksctl create iamserviceaccount --cluster eks-store --namespace kube-system \
  --name aws-load-balancer-controller --approve \
  --attach-policy-arn arn:aws:iam::$ACCOUNT:policy/AWSLoadBalancerControllerIAMPolicy
helm repo add eks https://aws.github.io/eks-charts && helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system \
  --set clusterName=eks-store --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
kubectl apply -f k8s/ingress.yaml
kubectl get ingress store        # ADDRESS = DNS do ALB
```

HTTPS: certificado no ACM + anotações `alb.ingress.kubernetes.io/certificate-arn` e
`alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'`. Lembre de apagar o Ingress antes do
teardown (o script já faz isso).

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Pod `Pending` | CPU/memória insuficiente nos nós | `kubectl describe pod`; reduza `maxReplicas` do HPA ou aumente o node group (`aws eks update-nodegroup-config --scaling-config desiredSize=3 ...`) |
| `ImagePullBackOff` | nome/tag errado, imagem só `arm64`, limite de pulls do Docker Hub | `kubectl describe pod`; publique `linux/amd64` no ECR (`./scripts/push-images.sh`) |
| `ExpiredToken` / `kubectl` pede login | sessão SSO expirou | `aws sso login` |
| HPA `cpu: <unknown>/50%` | metrics-server ausente ou iniciando | `kubectl get deploy -n kube-system metrics-server`; aguarde 1–2 min |
| `account` em `CrashLoopBackOff` | banco inacessível | `kubectl logs deploy/account`; Postgres pronto? endpoint/SG do RDS? |
| `EXTERNAL-IP <pending>` | ELB sendo criado / subnets sem tag | aguarde 2–3 min; o template já marca as subnets públicas |
| Teardown da VPC falha | ELB/ENI ainda existe | rode o teardown de novo; apague o Load Balancer órfão no console EC2 |
| 401 no navegador após login | cookie `Secure` em HTTP | use HTTPS (seção 10) ou teste via curl/smoke test |
