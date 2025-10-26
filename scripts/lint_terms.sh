#!/usr/bin/env bash
set -e
bad=$(git ls-files | egrep -v '(^docs/|package-lock.json|\.png$|\.jpg$|\.md$)' \
      | xargs -I{} sh -c "grep -nE '\bpairs\b' {} || true")
if [[ -n "$bad" ]]; then
  echo "Gebruik overal 'pair' (enkelvoud)."
  echo "$bad"
  exit 1
fi
