# Tradingbot Project Skeleton

Deze repo borgt dat we de **technische blueprint** strikt volgen via CI checks (schema's, lint, infra-validaties).

## Snelstart
1. Upload deze zip naar de server: `/srv/trading/upload`
2. Pak uit:
   ```bash
   cd /srv/trading
   unzip upload/tradingbot_project_skeleton.zip -d tradingbot
   cd tradingbot
   ```
3. Run lokale checks:
   ```bash
   make ci || true
   ```
4. Init git en commit:
   ```bash
   git init
   git add .
   git commit -m "init skeleton"
   ```

## Belangrijk
- Blueprint file: `docs/tradingbot_technical_blueprint.md` (hash gepind in `docs/.blueprint.sha256`).
- Event JSON-schema's in `schemas/`.
- Samples voor CI in `ci/samples/`.
- Infra checks valideren Caddyfile en Prometheus config.

