#!/usr/bin/env bash
# Compila e testa todos os módulos, um por vez, com o Maven Wrapper (./mvnw).
# Sem Java instalado no host? O mvnw roda dentro de um container eclipse-temurin:25-jdk.
#   ./scripts/build.sh                 # todos os módulos
#   ./scripts/build.sh gateway-service # só um
set -euo pipefail
cd "$(dirname "$0")/../api"

INTERFACES=(account auth exchange)                                      # vão para o ~/.m2 (mvn install)
SERVICES=(account-service auth-service exchange-service gateway-service) # geram target/*.jar
if (( $# )); then MODULES=("$@"); else MODULES=("${INTERFACES[@]}" "${SERVICES[@]}"); fi

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

for m in "${MODULES[@]}"; do
  guard
  echo "==> $m"
  if [[ " ${INTERFACES[*]} " == *" $m "* ]]; then mvnw "$m" clean install; else mvnw "$m" clean package; fi
done
