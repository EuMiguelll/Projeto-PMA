#!/usr/bin/env bash
# Compila e testa todos os módulos, um por vez: os Java com o Maven Wrapper (./mvnw) e o
# exchange-py (FastAPI) com o uv + pytest. Sem Java ou uv no host? Rodam dentro de um container
# (eclipse-temurin:25-jdk / ghcr.io/astral-sh/uv).
#   ./scripts/build.sh                 # todos os módulos
#   ./scripts/build.sh gateway-service # só um (ou: ./scripts/build.sh exchange-py)
set -euo pipefail
cd "$(dirname "$0")/../api"

INTERFACES=(account auth exchange)                                      # vão para o ~/.m2 (mvn install)
SERVICES=(account-service auth-service exchange-service gateway-service) # geram target/*.jar (exchange-service: versão Java anterior)
PYTHON=(exchange-py)                                                    # uv sync + pytest (a imagem sai do docker compose)
if (( $# )); then MODULES=("$@"); else MODULES=("${INTERFACES[@]}" "${SERVICES[@]}" "${PYTHON[@]}"); fi

# Mac: só compila com load (1 min) < 5 e pressão de memória normal; espera se estiver alto
guard() {
  [[ "$(uname)" == Darwin ]] || return 0
  while :; do
    load=$(sysctl -n vm.loadavg | awk '{print int($2)}')
    pressure=$(sysctl -n kern.memorystatus_vm_pressure_level) # 1 = normal
    (( load < 5 && pressure == 1 )) && return 0
    echo "load=$load pressure=$pressure: aguardando 30 s..."; sleep 30
  done
}

BG=""; command -v taskpolicy >/dev/null && BG="taskpolicy -b" # prioridade baixa no Mac

mvnw() { # $1 = módulo, resto = goals
  local dir=$1; shift
  if java -version >/dev/null 2>&1; then
    (cd "$dir" && $BG ./mvnw -B -T 2 --no-transfer-progress "$@")
  else
    $BG docker run --rm --cpus 2 --memory 3g \
      -v "$PWD/$dir":/src -v "$HOME/.m2":/root/.m2 -w /src \
      eclipse-temurin:25-jdk ./mvnw -B -T 2 --no-transfer-progress "$@"
  fi
}

uvtest() { # $1 = módulo Python: dependências travadas no uv.lock e os testes (PTAX simulada, sem rede)
  if command -v uv >/dev/null 2>&1; then
    (cd "$1" && $BG uv sync --frozen && $BG uv run pytest -q)
  else
    $BG docker run --rm --cpus 2 -v "$PWD/$1":/src -w /src -e UV_PROJECT_ENVIRONMENT=/tmp/venv \
      ghcr.io/astral-sh/uv:0.11.32-python3.12-trixie-slim sh -c 'uv sync --frozen && uv run pytest -q'
  fi
}

for m in "${MODULES[@]}"; do
  guard
  echo "==> $m"
  if [[ " ${INTERFACES[*]} " == *" $m "* ]]; then mvnw "$m" clean install
  elif [[ " ${PYTHON[*]} " == *" $m "* ]]; then uvtest "$m"
  else mvnw "$m" clean package; fi
done
