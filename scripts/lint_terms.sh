#!/usr/bin/env bash
set -euo pipefail

# Vind alleen relevante projectbestanden (geen .git/.venv/binaries/docs/images)
files=$(find . \
  -type d \( -name .git -o -name .venv -o -name node_modules -o -name docs -o -name vendor \) -prune -false -o \
  -type f \
    ! -name '*.png' ! -name '*.jpg' ! -name '*.jpeg' ! -name '*.gif' \
    ! -name '*.pdf' ! -name '*.zip' ! -name '*.tar' ! -name '*.tar.gz' \
    ! -name '*.so'  ! -name '*.pyc' -print)

# Grep: behandel binaire files als 'no match' (voor de zekerheid)
bad=$(grep -RIn --binary-files=without-match '\bpairs\b' $files || true)

if [[ -n "$bad" ]]; then
  echo "Gebruik overal 'pair' (enkelvoud)."
  echo "$bad"
  exit 1
fi
