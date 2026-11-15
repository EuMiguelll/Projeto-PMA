# Teste de carga

--8<-- "load-test/README.md:3:"

## Resultado no Kubernetes local (kind)

Antes de gastar no EKS, os mesmos manifests e o mesmo `k8s/deploy.sh` foram executados num
cluster **kind** (Kubernetes 1.37, 1 nó, metrics-server com `--kubelet-insecure-tls`) em
15/11/2026:

| Etapa | Resultado |
|-------|-----------|
| `DOCKERHUB_USERNAME=local ./k8s/deploy.sh` | 4 serviços + Postgres + Redis `Running`, probes OK |
| `./scripts/smoke-test.sh http://localhost:18080` (via `port-forward svc/gateway`) | **15/15 OK** |
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
