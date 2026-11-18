#!/usr/bin/env bash
# Verificacao conservadora e somente leitura, a partir de qualquer diretorio.
# Nao exibe valores de credenciais; nao substitui revisao manual.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
printf 'Revisao pre-publicacao - AI Support Flow\nRaiz: %s\n' "$ROOT"
sensitive=(.env backend/.env frontend/.env asf-backup-v02.sqlite backend/.venv-stage8 frontend/node_modules frontend/dist frontend/_etapa8 _etapa8)
for item in "${sensitive[@]}"; do
  if [[ -e "$item" ]]; then exists=sim; else exists=nao; fi
  ignored='indisponivel (sem repositorio Git)'
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git check-ignore -q -- "$item"; then ignored=sim; else ignored='nao/nao se aplica'; fi
  fi
  printf '%-32s existe=%-4s ignorado=%s\n' "$item" "$exists" "$ignored"
done
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  found=0
  while IFS= read -r -d '' item; do
    if [[ "$item" =~ (^|/)(\.env($|\.)|\.venv|node_modules|_etapa[0-9]+|\.n8n|.*\.sqlite(-.*)?$|.*\.db$|asf-backup|credentials.*\.json$) ]]; then
      if (( found == 0 )); then printf 'ATENCAO: arquivos possivelmente sensiveis ja rastreados:\n'; fi
      printf '  %s\n' "$item"; found=1
    fi
  done < <(git ls-files -z)
  if (( found == 0 )); then printf 'Nenhum caminho de alto risco identificado entre arquivos rastreados.\n'; fi
  printf 'Revise MANUALMENTE: git diff --cached --name-only\n'
else
  printf 'Repositorio Git nao inicializado ou Git indisponivel; revise manualmente.\n'
fi
printf 'ATENCAO: este script nao identifica segredos incluidos dentro de arquivos-fonte.\n'
