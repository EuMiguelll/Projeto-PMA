# AWS e EKS

## Infraestrutura

A topologia é a da página *EKS* do enunciado: uma VPC em **us-east-2** com 2 subnets
públicas (load balancer) e 2 privadas (pods/nós) em duas zonas de disponibilidade, criada pelo
template CloudFormation `amazon-eks-vpc-private-subnets.yaml` (copiado em `aws/`).

```mermaid
flowchart TB
    user([Usuário]) --> elb
    subgraph region [us-east-2]
        subgraph vpc [VPC 192.168.0.0/16 — CloudFormation]
            subgraph az1 [AZ a]
                pub1["Subnet pública<br/>192.168.0.0/18<br/>ELB · NAT GW"]
                priv1["Subnet privada<br/>192.168.128.0/18<br/>nó t3.medium"]
            end
            subgraph az2 [AZ b]
                pub2["Subnet pública<br/>192.168.64.0/18<br/>ELB · NAT GW"]
                priv2["Subnet privada<br/>192.168.192.0/18<br/>nó t3.medium"]
            end
        end
        cp["EKS control plane<br/>(gerenciado pela AWS)"]
        rds[("RDS PostgreSQL 17<br/>db.t4g.micro")]
        ecr[["Amazon ECR<br/>4 repositórios"]]
    end
    elb["Classic Load Balancer<br/>Service gateway"] --> priv1 & priv2
    priv1 & priv2 -.-> cp
    priv1 & priv2 -.-> rds
    priv1 & priv2 -.->|pull| ecr
    priv1 -->|NAT| pub1
    priv2 -->|NAT| pub2
    pub1 & pub2 --> igw([Internet Gateway]) --> awesome[[AwesomeAPI]]
```

| Script | O que faz |
|--------|-----------|
| `aws/eks-create.sh` | VPC (CloudFormation) → `eksClusterRole` → cluster `eks-store` → `eksNodeRole` (CNI, WorkerNode, ECR read-only) → node group `2 x t3.medium` nas subnets privadas → kubeconfig → metrics-server |
| `scripts/push-images.sh` | cria os repositórios no **ECR** (scan on push) e publica as 4 imagens `amd64` + `arm64` |
| `aws/rds-create.sh` | RDS PostgreSQL 17 `db.t4g.micro` privado, SG liberando 5432 só para os nós |
| `k8s/deploy.sh` | Redis e os 4 serviços com as imagens do ECR; segredos reais (JWT, senha do RDS); espera os rollouts |
| `aws/eks-teardown.sh` | apaga ELB → RDS → node group → cluster → VPC → repositórios do ECR |

O passo a passo completo, com conferências e problemas comuns, está no
[AWS Runbook](runbook.md).

## Deploy real no EKS (15/11/2026)

Executado na conta AWS do grupo (IAM Identity Center/SSO, papel `AdministratorAccess`), região
**us-east-2**, seguindo o [AWS Runbook](runbook.md) do começo ao fim:

| Recurso | Resultado |
|---------|-----------|
| VPC (CloudFormation `eks-store-vpc`) | 2 subnets públicas + 2 privadas em `us-east-2a`/`us-east-2b`, 2 NAT Gateways |
| Cluster `eks-store` | **ACTIVE**, Kubernetes **1.37**, endpoint público, *access entries* |
| Node group `eks-store-nodes` | **2 × `t3.medium`** (mín. 2, máx. 3), Amazon Linux 2023, só nas subnets privadas (`192.168.149.x` e `192.168.243.x`) |
| Banco | **Amazon RDS** PostgreSQL **17.9**, `db.t4g.micro`, 20 GB gp3, Single-AZ, **sem IP público**; o Flyway criou o schema `accounts` no primeiro start |
| Imagens | **Amazon ECR** da conta: `account-service`, `auth-service`, `exchange-service`, `gateway-service` (`amd64` + `arm64`, scan on push) |
| Load Balancer | Classic LB do Service `gateway`: **<http://a0fe1d39fd35640c4b0de61fe105bdb5-64525269.us-east-2.elb.amazonaws.com/info>** (portas 80 e 8080) |
| Smoke test pelo ELB | **11/14** — todo o fluxo de conta, login, JWT, rotas seguras e cache; as 3 verificações de câmbio falham porque a AwesomeAPI recusa IPs da AWS sem API key (abaixo) |
| HPA (busybox do enunciado) | gateway **1 → 4 → 8 → 10 réplicas** em ~80 s — [Teste de carga](load-testing.md#resultado-no-eks) |

Por que **2 nós**: 1 `t3.medium` (1930m CPU / 3,2 GiB alocáveis) comporta os 5 pods da
aplicação, mas o HPA do gateway só conseguiria subir mais 2–3 réplicas antes de ficarem
`Pending` por memória (cada réplica pede 384 Mi). Com 2 nós o gateway chegou a 10 réplicas com
os nós a 42 % / 26 % de CPU e ~60 % de memória.

!!! warning "Câmbio na AWS: AwesomeAPI devolve `429 QuotaExceeded` sem API key"
    Do Mac, `GET https://economia.awesomeapi.com.br/json/last/USD-BRL` responde 200; dos dois NAT
    Gateways da VPC, a mesma chamada devolve `429 {"code":"QuotaExceeded"}` desde a primeira
    requisição (os IPs da AWS já chegam com a cota sem chave estourada). O exchange
    se comporta como projetado: retry, circuit breaker e **503 rápido** no lugar de travar. A
    correção é a API key gratuita (100 mil requisições/mês): o exchange envia o header
    `x-api-key` quando existe `EXCHANGE_PROVIDER_TOKEN`, e o `deploy.sh` cria o Secret
    `exchange-secrets` com ela (`EXCHANGE_PROVIDER_TOKEN=<chave> ./k8s/deploy.sh`), sem passar pelo git.

??? example "Saídas: `kubectl get nodes/pods/svc/hpa`, `kubectl top`, EKS, RDS e ECR"

    ```text
    --8<-- "docs/evidencias/eks-deploy.txt"
    ```

??? example "Smoke test pelo Load Balancer"

    ```text
    --8<-- "docs/evidencias/smoke-test.txt"
    ```

Os IDs da conta e o identificador do endpoint do RDS foram trocados por `<ACCOUNT_ID>` e `<id>`
nas evidências: nada que identifique a conta vai para o repositório. Os scripts descobrem a
conta em tempo de execução (`aws sts get-caller-identity`).

## Manifests Kubernetes

Cada repositório de serviço tem o seu `k8s/k8s.yaml` (como pede o exercício MiniKube) com
**Secret** (quando há segredo), **ConfigMap**, **Deployment**, **Service** e
**HorizontalPodAutoscaler**. A infraestrutura compartilhada fica no repositório principal:

| Arquivo | Recursos |
|---------|----------|
| `api/account-service/k8s/k8s.yaml` | Secret (usuário/senha do banco), ConfigMap (host, porta, base, Redis), Deployment, Service `ClusterIP`, HPA 1–3 |
| `api/auth-service/k8s/k8s.yaml` | Secret (`JWT_SECRET_KEY`), ConfigMap, Deployment, Service `ClusterIP`, HPA 1–3 |
| `api/exchange-service/k8s/k8s.yaml` | ConfigMap (Redis, URL do provedor), Secret opcional `exchange-secrets` (API key, criado pelo `deploy.sh`), Deployment, Service `ClusterIP`, HPA 1–3 |
| `api/gateway-service/k8s/k8s.yaml` | ConfigMap (Redis, rate limit), Deployment, Service **`LoadBalancer`** (portas 80 e 8080), HPA **1–10** |
| `k8s/postgres.yaml` | Secret, ConfigMap, Deployment, Service do Postgres (sem volume, como no hands-on 5) |
| `k8s/redis.yaml` | Deployment + Service do Redis (64 MB, LRU) |
| `k8s/ingress.yaml` | (opcional) Ingress ALB — requer o AWS Load Balancer Controller |

??? example "api/gateway-service/k8s/k8s.yaml"

    ```yaml
    --8<-- "api/gateway-service/k8s/k8s.yaml"
    ```

??? example "api/account-service/k8s/k8s.yaml"

    ```yaml
    --8<-- "api/account-service/k8s/k8s.yaml"
    ```

Escolhas de configuração:

- **Recursos**: `requests` 100m CPU (gateway: 200m) e 384 Mi; `limits` 1 CPU e 512 Mi. O HPA
  calcula a utilização sobre o *request*, então 50 % ≈ 100m de CPU no gateway.
- **Probes**: `startupProbe` (até 3 min para a JVM subir com pouca CPU), `livenessProbe` e
  `readinessProbe` nos health groups do Actuator — o Service só manda tráfego para pods prontos e
  o rolling update não derruba a API.
- **Imagens**: `DOCKERHUB_USER/<serviço>-service` nos manifests; o `deploy.sh` troca o prefixo
  pelo registry do **ECR** da conta (ou por um usuário do Docker Hub). Multi-arch (`amd64` para os
  nós t3, `arm64` para Mac/Graviton). `imagePullPolicy: IfNotPresent` porque o CI faz deploy com
  a tag imutável `:<sha>`. Os nós baixam do ECR pela role `eksNodeRole`
  (`AmazonEC2ContainerRegistryReadOnly`), sem `imagePullSecrets`.
- **Service do gateway** nas portas 80 e 8080: `http://gateway/info` (o busybox do enunciado) e
  `http://<elb>:8080/info` (hands-on 5) funcionam.
- **`enableServiceLinks: false`**: sem isso o Kubernetes injeta `REDIS_PORT=tcp://<ip>:6379`
  (do Service `redis`) e o Spring falha ao converter a porta — achado no teste em kind
  ([Teste de carga](load-testing.md)).
- **Segredos**: os manifests trazem valores de desenvolvimento; o `deploy.sh` os sobrescreve
  (`JWT_SECRET_KEY` aleatória, senha do RDS gerada com `openssl rand` só no shell, API key da
  AwesomeAPI).

## Banco de dados: Postgres no cluster ou RDS

| | Postgres no cluster (kind/minikube) | **Amazon RDS** (`aws/rds-create.sh`) — **usado no EKS** |
|-|------------------------------|----------------------------------|
| Modelo | IaaS/CaaS — nós cuidamos | **PaaS** — AWS cuida de patch, backup, failover |
| Persistência | nenhuma (pod recriado = dados perdidos) | EBS gp3 + backups automáticos |
| Custo | ~0 (usa o nó) | + US$ 14/mês (`db.t4g.micro` + 20 GB) |
| Uso | kind / minikube | EKS (o enunciado pede **RDS ou DynamoDB**) |

O RDS `db.t4g.micro` Single-AZ é a opção mais barata que cumpre o enunciado (≈ US$ 0,016/h).
Trocar é só passar `DATABASE_HOST` ao `deploy.sh`: o `account-service` lê host/porta/base do
ConfigMap e usuário/senha do Secret, e o **Flyway** cria o schema no primeiro start.
