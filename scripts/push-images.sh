#!/usr/bin/env bash
# Publica as 4 imagens (linux/amd64 para os nós t3 do EKS + linux/arm64), sem o CI.
#   Amazon ECR da conta do `aws` CLI (padrão): ./scripts/build.sh && ./scripts/push-images.sh
#   Docker Hub: docker login && DOCKERHUB_USERNAME=<usuario> ./scripts/push-images.sh
set -euo pipefail
cd "$(dirname "$0")/../api"
REGISTRY=${DOCKERHUB_USERNAME:-}
if [[ -z "$REGISTRY" ]]; then
  REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION:-us-east-2}.amazonaws.com
  aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
fi
for s in account auth exchange gateway; do
  if [[ -z "${DOCKERHUB_USERNAME:-}" ]]; then
    aws ecr describe-repositories --repository-names "$s-service" >/dev/null 2>&1 ||
      aws ecr create-repository --repository-name "$s-service" --image-scanning-configuration scanOnPush=true >/dev/null
  fi
  docker buildx build --platform linux/amd64,linux/arm64 --push -t "$REGISTRY/$s-service:latest" "$s-service"
done
