# Teste de carga + HPA (roteiro do vídeo)

Objetivo (página *Load Testing* do enunciado): gravar **o teste de carga rodando** e **o HPA
escalando** o gateway. O alvo é `GET /info` do gateway — aberto (sem JWT) e fora do rate
limiting, então a carga vira CPU e não `429`.

## Pré-requisitos

- Plataforma no ar (`./k8s/deploy.sh`) e **metrics-server** (o `eks-create.sh` instala).
- `kubectl` apontando para o cluster: `aws eks update-kubeconfig --name eks-store` (com SSO
  expirado: `aws sso login`).
- HPA do gateway já vem no manifest (`api/gateway-service/k8s/k8s.yaml`):
  CPU 50 % do *request* (200m), `minReplicas: 1`, `maxReplicas: 10` — equivalente ao
  `kubectl autoscale deployment gateway --cpu-percent=50 --min=1 --max=10` do enunciado.

## Os 3 terminais

=== "1. HPA"

    ```bash
    kubectl get hpa gateway -w
    # NAME      REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS
    # gateway   Deployment/gateway   cpu: 2%/50%   1         10        1
    ```

=== "2. Pods"

    ```bash
    kubectl get pods -l app=gateway -o wide -w
    ```

(`-w` é o *watch* nativo do kubectl: imprime uma linha nova a cada mudança; o macOS não traz o
comando `watch`.)

=== "3. Carga (busybox do enunciado)"

    ```bash
    ./load-test/busybox.sh
    # = kubectl run -i --tty load-generator --rm --image=busybox:1.28 --restart=Never -- \
    #     /bin/sh -c "while sleep 0.01; do wget -q -O- http://gateway/info; done"   (x4 em paralelo)
    # Ctrl+C para parar. Variáveis: SLEEP=0.005 WORKERS=8 TARGET=http://gateway/health-check
    ```

## Alternativa: k6 (de fora do cluster, pelo ELB)

```bash
ELB=$(kubectl get svc gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
docker run --rm -i -e BASE_URL=http://$ELB -e VUS=150 grafana/k6 run - < load-test/k6.js
# local (docker compose): -e BASE_URL=http://host.docker.internal:8080 -e VUS=20 -e RAMP=20s -e HOLD=1m
```

Cenários: `info` (rampa de VUs no `/info`, alvo do HPA) e `user_flow` (login → `/auth/me` →
`/exchanges/USD/BRL`, que exercita JWT, cache Redis e o rate limiting — `429` é esperado).
O resumo final mostra `http_reqs`, latência p(95) e os *checks*.

## Roteiro de gravação (≈ 1 min de tela)

Tempos medidos no EKS (2 × `t3.medium`) em 15/11/2026:

| Tempo | Tela | Fala (resumo) |
|------:|------|---------------|
| 0:00 | 3 terminais lado a lado, HPA em `1%/50%`, 1 pod | "Gateway no EKS com HPA: 50 % de CPU, de 1 a 10 réplicas." |
| 0:10 | inicia `./load-test/busybox.sh` | "Carga de dentro do cluster no /info, 4 loops sem pausa." |
| 0:40 | TARGETS sobe para `~160%/50%` | "A CPU passa do alvo; o HPA calcula novas réplicas." |
| 0:55 | `REPLICAS` 4, pods `ContainerCreating` → `Running` | "Novas réplicas sobem; o Service distribui a carga." |
| 1:30 | 8 → **10** réplicas, TARGETS cai para `30–45%` | "Com mais pods, a CPU por pod fica abaixo do alvo." |
| 1:45 | Ctrl+C na carga | "Fim da carga; depois da janela de estabilização (~4–6 min) o HPA volta para 1." |

Dicas: `kubectl top pods -l app=gateway` mostra a CPU por pod; o scale-down é lento de propósito
(`behavior.scaleDown.stabilizationWindowSeconds` = 300 s por padrão). Para mostrar o
scale-down no vídeo, acelere a gravação nesse trecho. Para recomeçar do zero entre tomadas:
`kubectl scale deployment gateway --replicas=1` (o HPA aceita, já que está sem carga).
