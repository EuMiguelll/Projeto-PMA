#!/usr/bin/env bash
# Publica no GitHub: os 7 módulos na conta do Enzo (login com "canavero") e o repositório
# principal do grupo em $MAIN. Cria os repositórios dos módulos, faz push deles, aponta os submódulos para as URLs do
# GitHub, faz push do repositório principal, liga o GitHub Pages e mostra o GitHub Actions.
#   ./publish.sh
# Opcional (liga o job de imagem do CI): DOCKERHUB_USERNAME=<user> DOCKERHUB_TOKEN=<token> ./publish.sh
# Só usa a conta cujo login contém "canavero". A conta ativa do gh é restaurada no final.
set -euo pipefail
cd "$(dirname "$0")"
MODULES=(account auth exchange account-service auth-service exchange-service gateway-service)
MAIN=${MAIN_REPO:-EuMiguelll/Projeto-PMA} # repositório principal do grupo (o da planilha da disciplina)

accounts() { gh auth status -h github.com --json hosts --jq ".hosts[\"github.com\"][] | $1"; }
OWNER=$(accounts 'select(.login | test("canavero"; "i")) | .login' | head -1)
if [[ -z "$OWNER" ]]; then
  echo "A conta 'canavero' não está logada no gh. Rode: gh auth login -h github.com -s workflow" >&2
  exit 1
fi
if [[ "$(accounts "select(.login == \"$OWNER\") | .scopes")" != *workflow* ]]; then
  echo "A conta $OWNER precisa do escopo 'workflow' (para enviar .github/workflows). Rode:" >&2
  echo "  gh auth switch -h github.com -u $OWNER && gh auth refresh -h github.com -s workflow" >&2
  exit 1
fi
previous=$(accounts 'select(.active) | .login')
trap 'gh auth switch -h github.com -u "$previous" >/dev/null 2>&1 || true' EXIT
gh auth switch -h github.com -u "$OWNER"

create() { gh repo view "$OWNER/$1" >/dev/null 2>&1 || gh repo create "$OWNER/$1" --public -d "Projeto Store (Plataformas Insper 2026.2) — $1"; }
# força o gh como credencial (o keychain pode ter o token de outra conta)
push() { git -C "$1" -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin main; }

for m in "${MODULES[@]}"; do
  create "$m"
  if [[ "$m" == *-service && -n "${DOCKERHUB_USERNAME:-}" && -n "${DOCKERHUB_TOKEN:-}" ]]; then
    gh variable set DOCKERHUB_USERNAME -R "$OWNER/$m" -b "$DOCKERHUB_USERNAME"
    gh secret set DOCKERHUB_TOKEN -R "$OWNER/$m" -b "$DOCKERHUB_TOKEN"
  fi
  git -C "api/$m" remote set-url origin "https://github.com/$OWNER/$m.git"
  push "api/$m"
done

for m in "${MODULES[@]}"; do
  git config -f .gitmodules "submodule.api/$m.url" "https://github.com/$OWNER/$m.git"
done
git submodule sync --quiet
perl -pi -e "s/\bOWNER\b/$OWNER/g" mkdocs.yml README.md presentation/slides.md docs/*.md docs/projeto/*.md
git add -A
git diff --cached --quiet || git commit -q -m "Publica no GitHub ($OWNER): submódulos e links"
git remote set-url origin "https://github.com/$MAIN.git"
push .

echo "Aguardando o workflow 'docs' criar a branch gh-pages (até 10 min)..."
for _ in $(seq 60); do
  gh api "repos/$MAIN/branches/gh-pages" >/dev/null 2>&1 && break
  sleep 10
done
pages=(-f build_type=legacy -f 'source[branch]=gh-pages' -f 'source[path]=/')
gh api -X POST "repos/$MAIN/pages" "${pages[@]}" >/dev/null 2>&1 \
  || gh api -X PUT "repos/$MAIN/pages" "${pages[@]}" >/dev/null 2>&1 \
  || echo "AVISO: não consegui ligar o Pages (veja o workflow 'docs'); o dono de $MAIN liga em Settings > Pages > branch gh-pages"

for r in "${MODULES[@]/#/$OWNER/}" "$MAIN"; do
  echo "== $r: https://github.com/$r"
  gh run list -R "$r" -L 3
done
echo "Documentação: https://$(tr '[:upper:]' '[:lower:]' <<< "${MAIN%/*}").github.io/${MAIN#*/}/"
