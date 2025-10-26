# Security Policy

## Supported versions
The `main` branch receives security updates.

## Reporting a vulnerability
Please email **davelaar82@gmail.com** with a minimal reproduction if possible.
We aim to acknowledge within 72 hours.

## Secrets & credentials
- Do not commit secrets to the repo.
- CI uses the GitHub Secret `LE_EMAIL` for Caddy TLS validation only.
- Runtime credentials remain on the server under `/root/trading-secrets.txt` (not in Git).

## Dependencies
This repo pins CI tools to official Docker images (`caddy:latest`, `prom/prometheus:latest`).
