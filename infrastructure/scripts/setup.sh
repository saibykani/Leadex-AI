#!/usr/bin/env bash
# One-time local setup: .env (random JWT_SECRET), api venv + dev deps, web deps.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PY="$(command -v python3 || command -v python)"

if [ ! -f .env ]; then
  cp .env.example .env
  secret="$("$PY" -c 'import secrets;print(secrets.token_urlsafe(48))')"
  sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=$secret|" .env && rm -f .env.bak
  echo "Created .env with a random JWT_SECRET"
else
  echo ".env already exists; leaving it unchanged"
fi

cd "$ROOT/apps/api"
[ -d .venv ] || "$PY" -m venv .venv
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
fi
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

cd "$ROOT/apps/web"
npm install

echo "Setup complete."
