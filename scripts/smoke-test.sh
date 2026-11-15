#!/usr/bin/env bash
# Teste ponta a ponta pelo gateway: registro -> login -> rotas seguras -> exchange.
#   ./scripts/smoke-test.sh                      # local (docker compose)
#   ./scripts/smoke-test.sh http://<elb-dns>:8080 # EKS
set -uo pipefail
BASE=${1:-http://localhost:8080}
EMAIL="smoke.$(date +%s)@insper.edu.br"
JSON='Content-Type: application/json'
FAIL=0
# corpos em variáveis: o bash 3.2 do macOS expande {a,b} dentro de "$(...)"
REGISTER=$(printf '{"name":"Smoke Test","email":"%s","password":"123@321"}' "$EMAIL")
LOGIN=$(printf '{"email":"%s","password":"123@321"}' "$EMAIL")
WRONG=$(printf '{"email":"%s","password":"errada"}' "$EMAIL")

check() { # descrição esperado obtido
  if [[ "$2" == "$3" ]]; then echo "✅ $1 -> $3"; else echo "❌ $1 -> esperado $2, obtido $3"; FAIL=1; fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

# espera a cadeia gateway -> auth -> account ficar pronta (login inválido = 401)
for _ in $(seq 60); do
  [[ "$(code -X POST "$BASE/auth/login" -H "$JSON" -d "$WRONG")" == 401 ]] && break
  sleep 2
done

check "GET /health-check (aberto)" 200 "$(code "$BASE/health-check")"
check "GET /info (aberto)" 200 "$(code "$BASE/info")"
check "POST /auth/register" 200 "$(code -X POST "$BASE/auth/register" -H "$JSON" -d "$REGISTER")"
check "POST /auth/register (email repetido)" 409 "$(code -X POST "$BASE/auth/register" -H "$JSON" -d "$REGISTER")"
check "POST /auth/login (senha errada)" 401 "$(code -X POST "$BASE/auth/login" -H "$JSON" -d "$WRONG")"

TOKEN=$(curl -s -D - -o /dev/null -X POST "$BASE/auth/login" -H "$JSON" -d "$LOGIN" | sed -n 's/^[Ss]et-[Cc]ookie: __store_jwt_token=\([^;]*\).*/\1/p')
check "POST /auth/login devolve cookie JWT" yes "$([[ -n "$TOKEN" ]] && echo yes || echo no)"
COOKIE="__store_jwt_token=$TOKEN"

check "GET /accounts sem cookie" 401 "$(code "$BASE/accounts")"
check "GET /accounts com token forjado" 401 "$(code -b "__store_jwt_token=a.b.c" "$BASE/accounts")"
ME=$(curl -s -b "$COOKIE" "$BASE/auth/me"); ID=$(jq -r .id <<<"$ME" 2>/dev/null)
check "GET /auth/me" "$EMAIL" "$(jq -r .email <<<"$ME" 2>/dev/null)"
check "GET /accounts/{id} (1ª vez: banco)" 200 "$(code -b "$COOKIE" "$BASE/accounts/$ID")"
check "GET /accounts/{id} (2ª vez: cache Redis)" 200 "$(code -b "$COOKIE" "$BASE/accounts/$ID")"

EX=$(curl -s -b "$COOKIE" -H 'id-account: hacker' "$BASE/exchanges/USD/BRL")
echo "   exchange: $EX"
check "GET /exchanges/USD/BRL tem sell/buy" yes "$(jq -e '.sell > 0 and .buy > 0' <<<"$EX" >/dev/null 2>&1 && echo yes || echo no)"
check "id-account vem do token (header forjado descartado)" "${ID:-sem-id}" "$(jq -r '."id-account"' <<<"$EX" 2>/dev/null)"
check "GET /exchanges/XXX/YYY (par inválido)" 404 "$(code -b "$COOKIE" "$BASE/exchanges/XXX/YYY")"

[[ $FAIL == 0 ]] && echo "SMOKE TEST OK" || echo "SMOKE TEST FALHOU"
exit $FAIL
