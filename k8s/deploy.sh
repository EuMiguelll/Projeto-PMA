#!/usr/bin/env bash
# Implanta a plataforma no cluster do contexto atual do kubectl (EKS, kind, minikube...).
#   ./k8s/deploy.sh                                  # imagens no Amazon ECR da conta do `aws` CLI
#   DOCKERHUB_USERNAME=<usuario> ./k8s/deploy.sh     # imagens no Docker Hub (ou "local" no kind)
# Opcionais:
#   JWT_SECRET_KEY=...            chave do JWT (padrão: gera uma aleatória)
#   DATABASE_HOST=<endpoint RDS>  usa o RDS em vez do Postgres no cluster
#   DATABASE_USERNAME / DATABASE_PASSWORD  credenciais do RDS
set -euo pipefail
cd "$(dirname "$0")/.."
# prefixo das imagens: usuário do Docker Hub ou registry do ECR (a conta não fica em nenhum arquivo)
REGISTRY=${DOCKERHUB_USERNAME:-$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION:-us-east-2}.amazonaws.com}

kubectl apply -f k8s/redis.yaml
if [[ -z "${DATABASE_HOST:-}" ]]; then
  kubectl apply -f k8s/postgres.yaml
  kubectl rollout status deployment/postgres --timeout=300s
fi

for s in account auth exchange gateway; do
  sed "s#DOCKERHUB_USER#$REGISTRY#g" "api/$s-service/k8s/k8s.yaml" | kubectl apply -f -
done

# segredos reais por cima dos valores de desenvolvimento dos manifests
apply_secret() { kubectl create secret generic "$@" --dry-run=client -o yaml | kubectl apply -f -; }
apply_secret auth-secrets --from-literal=JWT_SECRET_KEY="${JWT_SECRET_KEY:-$(openssl rand -base64 32)}"
if [[ -n "${DATABASE_HOST:-}" ]]; then
  kubectl patch configmap account-configmap -p "{\"data\":{\"DATABASE_HOST\":\"$DATABASE_HOST\"}}"
  apply_secret account-secrets \
    --from-literal=DATABASE_USERNAME="${DATABASE_USERNAME:-store}" \
    --from-literal=DATABASE_PASSWORD="${DATABASE_PASSWORD:?defina DATABASE_PASSWORD do RDS}"
fi
kubectl rollout restart deployment/auth deployment/account

for d in redis account auth exchange gateway; do kubectl rollout status deployment/$d --timeout=300s; done
kubectl get pods,svc,hpa
echo
lb=$(kubectl get svc gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}{.status.loadBalancer.ingress[0].ip}')
echo "Gateway: http://${lb:-<LoadBalancer pendente: kubectl get svc gateway -w>}/info"
echo "(o DNS do ELB leva 1-3 min para propagar; em kind/minikube use kubectl port-forward svc/gateway 8080:8080)"
