#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  source venv/bin/activate
  # upgrade minor libs if needed (safe)
  pip install --upgrade -r requirements.txt >/dev/null 2>&1 || true
fi
exec python -m app.main --config ./config/public.yml
