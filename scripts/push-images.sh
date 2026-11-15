#!/usr/bin/env bash
# Publica as 4 imagens no Docker Hub (linux/amd64 para os nós t3 do EKS + linux/arm64), sem o CI.
#   ./scripts/build.sh && docker login && DOCKERHUB_USERNAME=<usuario> ./scripts/push-images.sh
set -euo pipefail
: "${DOCKERHUB_USERNAME:?defina DOCKERHUB_USERNAME}"
cd "$(dirname "$0")/../api"
for s in account auth exchange gateway; do
  docker buildx build --platform linux/amd64,linux/arm64 --push \
    -t "$DOCKERHUB_USERNAME/$s-service:latest" "$s-service"
done
