#!/usr/bin/env bash
set -euo pipefail

: "${DOMAIN:=snapdiscounts.nl}"
: "${LE_EMAIL:=r.davelaar@icloud.com}"

COMPOSE="/srv/trading/compose/docker-compose.core.yml"

echo "==> Validatie vóór deploy..."
scripts/validate_infra.sh

echo "==> Deploy Caddyfile -> /srv/trading/config/Caddyfile"
install -m 644 config/Caddyfile /srv/trading/config/Caddyfile

echo "==> Deploy Prometheus config -> /srv/trading/prometheus/prometheus.yml"
install -m 644 prometheus/prometheus.yml /srv/trading/prometheus/prometheus.yml

echo "==> Services herstarten via docker compose"
docker compose -f "$COMPOSE" restart caddy || docker compose -f "$COMPOSE" up -d caddy
docker compose -f "$COMPOSE" restart prometheus || docker compose -f "$COMPOSE" up -d prometheus
docker compose -f "$COMPOSE" restart grafana || docker compose -f "$COMPOSE" up -d grafana

sleep 2

echo "==> Health-checks"
set +e
curl -fsS -I "https://$DOMAIN/" >/dev/null && echo "[OK] Root reachable"
curl -fsS -I "https://$DOMAIN/grafana/" >/dev/null && echo "[OK] Grafana reachable"
curl -fsS -I "https://$DOMAIN/prometheus/-/ready" >/dev/null && echo "[OK] Prometheus ready"
set -e

echo "==> Logs (laatste 10 regels)"
for s in caddy grafana prometheus; do
  echo "--- $s ---"
  docker logs "$s" --since=30s 2>&1 | tail -n 10 || true
done

echo "[DONE] Deploy afgerond voor DOMAIN=$DOMAIN"
