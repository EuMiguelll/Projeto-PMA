# Teste de carga

--8<-- "load-test/README.md:3:"

## Vídeo do teste de carga

<video controls preload="metadata" width="100%">
  <source src="../../videos/teste-de-carga-hpa.mp4" type="video/mp4">
</video>

[Baixar o vídeo](../videos/teste-de-carga-hpa.mp4) · 1 min 27 s, com os trechos de espera acelerados (a
velocidade aparece no canto superior direito).

Três painéis, como na página *Load Testing* da disciplina: `watch kubectl get hpa gateway`,
`watch kubectl get pods -l app=gateway` e o busybox do enunciado (`WORKERS=16 ./load-test/busybox.sh`).
Gravado em 16/11/2026 num cluster **kind** local, com os mesmos manifests e o mesmo `k8s/deploy.sh` do
EKS: o EKS já tinha mostrado o HPA de 1 para 10 em 15/11 (evidência abaixo), e gravar de novo na
nuvem só gastaria AWS.

| Hora (UTC) | HPA do gateway | O que aconteceu |
|-----------:|----------------|-----------------|
| 00:54:28 | 1 réplica, `cpu: 1%/50%` | o busybox começa (16 loops de `wget http://gateway/info`) |
| 00:55:11 | **4** (`cpu: 151%/50%`) | primeira escala, ≈ 45 s depois |
| 00:55:31 | **6** | |
| 00:55:41 | **10** (máximo) | ≈ 75 s após o início da carga |
| 00:56:57 | 10 | `Ctrl+C`: fim da carga |
| 01:02:13 → 01:02:43 | 10 → 9 → 3 → **2** | scale-down depois da janela de estabilização de 5 min |
| 01:07 | **1** | de volta ao mínimo |

## Resultado no EKS

Cluster `eks-store` (2 × `t3.medium`, us-east-2), 15/11/2026. Dois testes: o do enunciado
(busybox dentro do cluster) e o k6 pelo **Load Balancer público**.

### 1. busybox do enunciado → HPA de 1 para 10 réplicas

`./load-test/busybox.sh` (4 loops de `wget http://gateway/info` sem pausa) das 22:04:48 às
22:09:13 UTC:

| Hora (UTC) | HPA do gateway (`kubectl get hpa`) | O que aconteceu |
|-----------:|------------------------------------|-----------------|
| 22:04:38 | `cpu: 3%/50%`, 1 réplica | antes da carga |
| 22:05:18 | `cpu: 162%/50%` → **4** | primeira leitura com carga: `SuccessfulRescale New size: 4` |
| 22:06:11 | `cpu: 123%/50%` → **8** | as 4 réplicas ainda acima do alvo |
| 22:06:25 | `cpu: 88%/50%` → **10** | máximo do HPA, **~80 s após o início** |
| 22:07:30–22:09 | `cpu: 33–47%/50%`, 10 réplicas | estável: ~40–95m de CPU por pod, nós a 42 % e 20 % de CPU |
| 22:09:13 | — | fim da carga |
| 22:12:45–22:15:04 | 10 → 9 → 7 → 2 → **1** | scale-down depois da janela de estabilização (300 s desde a última recomendação alta) |

```text
NAME      REFERENCE            TARGETS        MINPODS   MAXPODS   REPLICAS
gateway   Deployment/gateway   cpu: 41%/50%   1         10        10
```

??? example "Evidência completa: linha do tempo, `kubectl top`, pods e eventos do HPA"

    ```text
    --8<-- "docs/evidencias/hpa-busybox.txt"
    ```

### 2. k6 pelo Load Balancer

`load-test/k6.js` com 100 VUs (rampa de 30 s, platô de 2 min) no `/info` + 2 usuários no fluxo
autenticado, contra `http://<elb>`. O k6 rodou como pod no próprio cluster (sem pesar no Mac),
mas pelo DNS público do ELB: as requisições saem pelo NAT e entram pelo Classic Load Balancer.

| Métrica | Resultado |
|---------|-----------|
| Requisições | **406.170** em ~3 min (**2.215 req/s**) |
| Latência `/info` | média 37 ms · mediana 22 ms · **p95 123 ms** · máx. 921 ms |
| Erros `/info` | **0,00 %** (thresholds `p(95)<800ms` e `rate<0.01` ✓) |
| Fluxo autenticado | login 100 % · `/auth/me` 98 % (2 de 180 falharam no pico) · câmbio 0 % (AwesomeAPI devolve 429 para a AWS, ver [AWS e EKS](eks.md#deploy-real-no-eks-15112026)) |
| HPA do gateway | 1 → 4 → 8 → **10 em ~47 s**; CPU por pod ainda em ~100–200 % no máximo de réplicas |

!!! warning "Limite encontrado: memória do node group"
    Com 5× mais carga que o busybox, os HPAs de `account`, `exchange` e `auth` também subiram, e
    os requests de memória chegaram a **97 % e 89 %** dos 2 nós: 2 réplicas do gateway e 1 do
    auth ficaram `Pending` (`0/2 nodes are available: 2 Insufficient memory`). O HPA escala
    **pods**, não **nós**: no EKS isso exige o Cluster Autoscaler ou o Karpenter (o node group já
    aceita até 3 nós). Outras saídas: nós `t3.large` (8 GiB), requests de memória menores
    para as JVMs ou `maxReplicas` coerente com a capacidade. Para o vídeo, o busybox do
    enunciado cabe nos 2 nós (10 réplicas, todas `Running`).

??? example "Evidência completa do k6 (resumo, HPA e pods `Pending`)"

    ```text
    --8<-- "docs/evidencias/k6-elb.txt"
    ```

## Resultado no Kubernetes local (kind)

Antes de gastar no EKS, os mesmos manifests e o mesmo `k8s/deploy.sh` foram executados num
cluster **kind** (Kubernetes 1.37, 1 nó, metrics-server com `--kubelet-insecure-tls`) em
15/11/2026:

| Etapa | Resultado |
|-------|-----------|
| `DOCKERHUB_USERNAME=local ./k8s/deploy.sh` | 4 serviços + Postgres + Redis `Running`, probes OK |
| `./scripts/smoke-test.sh http://localhost:18080` (via `port-forward svc/gateway`) | **14/14 OK** |
| busybox (4 workers, `http://gateway/info`) por 3 min | HPA do gateway: **1 → 4 réplicas** (`SuccessfulRescale ... cpu resource utilization above target`); com a carga dividida, ≈ 55m CPU por pod (29 % do *request*) e a escala estabilizou |

```text
NAME      REFERENCE            TARGETS        MINPODS   MAXPODS   REPLICAS
gateway   Deployment/gateway   cpu: 29%/50%   1         10        4
```

!!! bug "Problema encontrado pelo teste: `REDIS_PORT=tcp://10.96.x.x:6379`"
    No primeiro deploy, `account`, `exchange` e `gateway` entraram em `CrashLoopBackOff`:
    o Kubernetes injeta em todo pod variáveis de *service links* de cada Service — o Service
    `redis` gera `REDIS_PORT=tcp://<ip>:6379`, que colidiu com o `${REDIS_PORT:6379}` do
    `application.yaml` (*failed to convert java.lang.String to int*). No Docker Compose isso não
    acontece. Correção: `enableServiceLinks: false` nos Deployments.

!!! note "JVM × HPA"
    O pico de CPU da JVM na inicialização também conta para o HPA: após o `rollout restart`,
    `account` e `exchange` subiram para 2 réplicas sem carga. O `startupProbe` evita tráfego antes
    da hora, mas não esse efeito; em produção vale configurar `behavior.scaleUp` com janela de
    estabilização ou usar uma métrica de requisições (Prometheus Adapter/KEDA). A redução
    acontece sozinha após a janela padrão de 5 min.

## Scripts

=== "load-test/busybox.sh (enunciado)"

    ```bash
    --8<-- "load-test/busybox.sh"
    ```

=== "load-test/k6.js"

    ```javascript
    --8<-- "load-test/k6.js"
    ```
