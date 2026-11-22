#!/usr/bin/env bash
# Publica as 4 imagens (linux/amd64, a arquitetura dos nós t3 do EKS), sem o CI:
# account-service, auth-service, exchange-py (FastAPI) e gateway-service.
# PLATFORMS=linux/amd64,linux/arm64 gera também arm64 (dobra o armazenamento no ECR).
#   Amazon ECR da conta do `aws` CLI (padrão): ./scripts/build.sh && ./scripts/push-images.sh
#   Docker Hub: docker login && DOCKERHUB_USERNAME=<usuario> ./scripts/push-images.sh
set -euo pipefail
cd "$(dirname "$0")/../api"
REGISTRY=${DOCKERHUB_USERNAME:-}
if [[ -z "$REGISTRY" ]]; then
  REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION:-us-east-2}.amazonaws.com
  aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
fi
for s in account-service auth-service exchange-py gateway-service; do
  if [[ -z "${DOCKERHUB_USERNAME:-}" ]]; then
    aws ecr describe-repositories --repository-names "$s" >/dev/null 2>&1 ||
      aws ecr create-repository --repository-name "$s" --image-scanning-configuration scanOnPush=true >/dev/null
    # lifecycle: apaga imagens sem tag após 1 dia e mantém só as 3 últimas com tag
    aws ecr put-lifecycle-policy --repository-name "$s" --lifecycle-policy-text '{"rules":[
      {"rulePriority":1,"selection":{"tagStatus":"untagged","countType":"sinceImagePushed","countUnit":"days","countNumber":1},"action":{"type":"expire"}},
      {"rulePriority":2,"selection":{"tagStatus":"tagged","tagPatternList":["*"],"countType":"imageCountMoreThan","countNumber":3},"action":{"type":"expire"}}]}' >/dev/null
  fi
  docker buildx build --platform "${PLATFORMS:-linux/amd64}" --push -t "$REGISTRY/$s:latest" "$s"
done
