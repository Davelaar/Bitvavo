# Contributing

Thanks for your interest in improving this project! This repo contains the **infrastructure** for the Bitvavo Tradingbot.

## Quick start (development on the server)
```bash
# Validate infra locally
cd /srv/trading/tradingbot
make ci
```
## Branching & commits
- Work on short‑lived branches from `main` (`feat/*`, `fix/*`, `chore/*`).
- Conventional commits are preferred:
  - `feat: ...`, `fix: ...`, `chore: ...`, `docs: ...`, `ci: ...`

## Pull requests
1. Ensure `make ci` passes locally.
2. Add tests/samples if your change touches schemas or events.
3. Open a PR to `main` and fill in the PR template.
4. CI must be green before merge.

## Coding standards
- YAML: validated with `yamllint` (see CI).
- JSON samples: validated via `scripts/validate_events.py` (jsonschema).
- Caddy & Prometheus configs are validated via Dockerized tools (`caddy validate`, `promtool`).

## Secrets
- GitHub secret `LE_EMAIL` is used by CI for Caddy TLS validation.
- Never commit secrets. Use GitHub Secrets or server‑side `.env` files.
