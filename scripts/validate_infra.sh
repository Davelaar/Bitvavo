#!/usr/bin/env bash
set -euo pipefail

# Defaults voor env-substitutie in Caddyfile (overschrijfbaar)
: "${LE_EMAIL:=r.davelaar@icloud.com}"
: "${DOMAIN:=snapdiscounts.nl}"

if command -v docker >/dev/null 2>&1; then
  # Compose syntaxis checken
  docker compose -f compose/docker-compose.core.yml config >/dev/null

  # Caddyfile valideren mét env vars
  docker run --rm \
    -e LE_EMAIL="$LE_EMAIL" -e DOMAIN="$DOMAIN" \
    -v "$PWD/config/Caddyfile:/etc/caddy/Caddyfile" caddy:latest \
    caddy validate --config /etc/caddy/Caddyfile >/dev/null

  # Prometheus config valideren via promtool (entrypoint override)
  docker run --rm \
    --entrypoint promtool \
    -v "$PWD/prometheus:/etc/prometheus" prom/prometheus:latest \
    check config /etc/prometheus/prometheus.yml >/dev/null
fi

echo "[OK] Infra-config validatie afgerond voor DOMAIN=$DOMAIN"
