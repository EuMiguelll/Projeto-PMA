# AWS Runbook — do zero ao EKS (e de volta a zero)

Roteiro executável para subir a plataforma **Store** na AWS, gravar o teste de carga e
**desligar tudo**. Os scripts seguem a ordem do enunciado (páginas *AWS* e *EKS*):
VPC via CloudFormation (template `amazon-eks-vpc-private-subnets.yaml`) → role do cluster →
cluster EKS → role do node group → node group só nas subnets privadas → kubeconfig.

!!! danger "Isto custa dinheiro"
    Com 2 nós `t3.medium`, 2 NAT Gateways (do template) e 1 Load Balancer, o ambiente custa
    **≈ US$ 0,33/hora (≈ US$ 7,90/dia)** enquanto existir — mesmo parado.
    Planeje uma sessão de ~2–3 h (≈ US$ 1) e rode o **passo 9 (teardown)** no final.
    Detalhes na análise de custos (`docs/projeto/custos.md`).

| Passo | O quê | Tempo | Custo |
|------:|-------|------:|-------|
| 0 | Ferramentas | 5 min | — |
| 1 | Usuário IAM, access key, `aws configure`, alerta de orçamento | 10 min | — |
| 2 | Imagens no Docker Hub | 5 min | — |
| 3 | `./aws/eks-create.sh` (VPC + EKS + nós + metrics-server) | 20 min | começa a cobrar |
| 4 | (opcional) `./aws/rds-create.sh` | 10 min | + US$ 0,02/h |
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

Seguindo a página *AWS* do enunciado (nunca use o usuário root no dia a dia):

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
    As credenciais temporárias incluem `AWS_SESSION_TOKEN` (cadastre também no GitHub).

## 2. Imagens no Docker Hub

O EKS baixa as imagens `DOCKERHUB_USER/<serviço>-service`. Os nós são **x86 (t3)**, então a imagem
precisa de `linux/amd64` — os dois caminhos abaixo publicam `amd64` + `arm64`.

=== "Via CI (recomendado)"

    Em cada repositório de serviço (`account-service`, `auth-service`, `exchange-service`,
    `gateway-service`): *Settings → Secrets and variables → Actions*:

    - **Variable** `DOCKERHUB_USERNAME` = seu usuário do Docker Hub
    - **Secret** `DOCKERHUB_TOKEN` = token criado em *Docker Hub → Account settings → Personal access tokens* (Read & Write)

    Com o `gh`:

    ```bash
    for r in account-service auth-service exchange-service gateway-service; do
      gh variable set DOCKERHUB_USERNAME -b "<usuario>" -R "<owner>/$r"
      gh secret set DOCKERHUB_TOKEN -b "<token>" -R "<owner>/$r"
      gh workflow run ci.yml -R "<owner>/$r"
    done
    ```

=== "Manual (da sua máquina)"

    ```bash
    ./scripts/build.sh                                   # gera os target/*.jar
    docker login
    DOCKERHUB_USERNAME=<usuario> ./scripts/push-images.sh
    ```

## 3. Criar VPC + cluster EKS + node group

```bash
./aws/eks-create.sh            # padrão: us-east-2, cluster eks-store, 2 x t3.medium
# variáveis: AWS_REGION, CLUSTER, NODE_TYPE (ex.: t4g.medium), NODES
```

O script é idempotente (pode ser rodado de novo se cair no meio) e faz:

1. `aws cloudformation deploy` do template do enunciado → VPC `192.168.0.0/16`, 2 subnets
   públicas (load balancers, tag `kubernetes.io/role/elb`) e 2 privadas (pods, tag
   `kubernetes.io/role/internal-elb`) em duas AZs, 1 NAT Gateway por AZ;
2. role `eksClusterRole` com `AmazonEKSClusterPolicy`;
3. `aws eks create-cluster` (endpoint público, autenticação por *access entries*) e espera ficar `ACTIVE`;
4. role `eksNodeRole` com `AmazonEKS_CNI_Policy`, `AmazonEKSWorkerNodePolicy`,
   `AmazonEC2ContainerRegistryReadOnly` (as três do enunciado);
5. node group gerenciado **só nas subnets privadas**;
6. `aws eks update-kubeconfig --name eks-store` + **metrics-server** (o HPA depende dele).

Conferência:

```bash
kubectl config get-contexts
kubectl get nodes -o wide          # 2 nós Ready, IPs 192.168.128.x / 192.168.192.x (privados)
kubectl top nodes                  # metrics-server ok (leva ~1 min)
```

## 4. (Opcional) Banco gerenciado — Amazon RDS

Por padrão o Postgres roda **dentro do cluster** (`k8s/postgres.yaml`, mais barato, sem
persistência). Para usar o RDS (PaaS, backups, patching gerenciado):

```bash
DATABASE_PASSWORD='uma-senha-forte' ./aws/rds-create.sh
# imprime o DATABASE_HOST a usar no passo 5
```

Cria `db.t4g.micro` PostgreSQL 17, 20 GB gp3, Single-AZ, **sem IP público**, nas subnets privadas,
com security group liberando a porta 5432 só para os nós do EKS.

## 5. Implantar a plataforma

```bash
export DOCKERHUB_USERNAME=<usuario>
export JWT_SECRET_KEY=$(openssl rand -base64 32)       # guarde se quiser manter as sessões
./k8s/deploy.sh
# com RDS:
# DATABASE_HOST=<endpoint> DATABASE_PASSWORD='...' ./k8s/deploy.sh
```

O script aplica `k8s/redis.yaml`, `k8s/postgres.yaml` (se não houver RDS) e o
`api/<serviço>/k8s/k8s.yaml` de cada serviço (Secret, ConfigMap, Deployment, Service, HPA),
sobrescreve os segredos de desenvolvimento e espera os rollouts. No fim imprime a URL do ELB.

```bash
kubectl get pods,svc,hpa
kubectl get svc gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

## 6. Testar

```bash
ELB=$(kubectl get svc gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
curl http://$ELB/health-check          # {"hostname":"gateway-..."}
curl http://$ELB/info
./scripts/smoke-test.sh http://$ELB    # registro, login, rotas seguras, exchange
```

!!! note "Cookie `Secure` em HTTP"
    O login devolve o JWT em cookie `HttpOnly; Secure; SameSite=None` (como no hands-on 3).
    `curl`/k6/smoke test enviam o cookie explicitamente; **um navegador só o reenvia por HTTPS**
    (para isso: Ingress com ALB + certificado do ACM, seção 10).

## 7. CI/CD: deploy automático no EKS

O job `deploy` dos workflows faz `kubectl set image deployment/<serviço> <serviço>=<imagem>:<sha>`
e `kubectl rollout status`. Ele só roda se a variável `EKS_CLUSTER` existir. Crie um usuário
dedicado, com acesso mínimo:

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws iam create-user --user-name github-deployer
aws iam put-user-policy --user-name github-deployer --policy-name eks-describe \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"eks:DescribeCluster","Resource":"*"}]}'
aws iam create-access-key --user-name github-deployer          # anote AccessKeyId/SecretAccessKey
aws eks create-access-entry --cluster-name eks-store \
  --principal-arn arn:aws:iam::$ACCOUNT:user/github-deployer
aws eks associate-access-policy --cluster-name eks-store \
  --principal-arn arn:aws:iam::$ACCOUNT:user/github-deployer \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy \
  --access-scope type=namespace,namespaces=default
```

Cadastre nos 4 repositórios de serviço:

```bash
for r in account-service auth-service exchange-service gateway-service; do
  gh variable set EKS_CLUSTER -b eks-store -R "<owner>/$r"
  gh variable set AWS_REGION -b us-east-2 -R "<owner>/$r"
  gh secret set AWS_ACCESS_KEY_ID -b "<AccessKeyId>" -R "<owner>/$r"
  gh secret set AWS_SECRET_ACCESS_KEY -b "<SecretAccessKey>" -R "<owner>/$r"
done
```

Teste: um commit em `main` de qualquer serviço → Actions: **Build & Test → Docker Hub → Deploy EKS**.

## 8. Teste de carga e vídeo do HPA

Ver `load-test/README.md` (página *Teste de carga* do site) — 3 terminais (HPA, pods, gerador de carga
busybox do enunciado) e a alternativa com k6.

## 9. Teardown (obrigatório)

```bash
./aws/eks-teardown.sh
```

Remove, nesta ordem: Service `LoadBalancer`/Ingress (libera o ELB) → RDS (se houver) →
node group → cluster → stack da VPC (subnets, NAT Gateways, Elastic IPs). As roles IAM ficam
(não custam nada). Depois confira no console, região **us-east-2**:

- [ ] EKS → Clusters: vazio
- [ ] EC2 → Instances, Load Balancers, NAT Gateways, Elastic IPs, Volumes: vazios
- [ ] RDS → Databases: vazio
- [ ] CloudFormation → Stacks: sem `eks-store-vpc`
- [ ] (opcional) IAM → `github-deployer` → desative a access key

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
| `ImagePullBackOff` | nome/tag errado, imagem só `arm64`, limite de pulls do Docker Hub | confira `DOCKERHUB_USERNAME`, publique `linux/amd64`; use `imagePullSecrets` ou ECR |
| HPA `cpu: <unknown>/50%` | metrics-server ausente ou iniciando | `kubectl get deploy -n kube-system metrics-server`; aguarde 1–2 min |
| `account` em `CrashLoopBackOff` | banco inacessível | `kubectl logs deploy/account`; Postgres pronto? endpoint/SG do RDS? |
| `EXTERNAL-IP <pending>` | ELB sendo criado / subnets sem tag | aguarde 2–3 min; o template já marca as subnets públicas |
| Teardown da VPC falha | ELB/ENI ainda existe | rode o teardown de novo; apague o Load Balancer órfão no console EC2 |
| 401 no navegador após login | cookie `Secure` em HTTP | use HTTPS (seção 10) ou teste via curl/smoke test |
