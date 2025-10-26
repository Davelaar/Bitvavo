# Tradingbot CI/CD - Deploy pakket

Dit pakket is **geparametriseerd** voor:
- DOMAIN: `snapdiscounts.nl`
- LE_EMAIL: `r.davelaar@icloud.com`

## Snel starten (op de server)

1. Plaats/uitpakken in `/srv/trading/tradingbot/` (bijv. via Filestash).
2. Controleer dat `docker` werkt en dat je compose file staat op `/srv/trading/compose/docker-compose.core.yml`.
3. Run:
   ```bash
   cd /srv/trading/tradingbot
   make ci
   make deploy
   make status
   ```

### Wat doet `make deploy`?
- Valideert Caddyfile + Prometheus config in containers.
- Kopieert `config/Caddyfile` naar `/srv/trading/config/Caddyfile`.
- Kopieert `prometheus/prometheus.yml` naar `/srv/trading/prometheus/prometheus.yml`.
- Herstart `caddy`, `prometheus`, `grafana` via docker compose.
- Doet health checks op:
  - https://snapdiscounts.nl/
  - https://snapdiscounts.nl/grafana/
  - https://snapdiscounts.nl/prometheus/-/ready

## GitHub Actions
De workflow gebruikt `secrets.DOMAIN` en `secrets.LE_EMAIL` als ze aanwezig zijn; anders vallen ze terug op de waarden hierboven.
