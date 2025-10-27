Market Selection Overlay (compose v3-style, no 'version:' key).

Plaats deze map als ZIP in: /srv/trading/upload
Unzip in: /srv/trading/upload/market_selection_compose_overlay_v3

Voorbeeld deploy (volg jouw project-instructies – dit is alleen ter referentie):
  docker compose -f /srv/trading/compose/docker-compose.core.yml                  -f /srv/trading/upload/market_selection_compose_overlay_v3/compose/docker-compose.core.market_selection.yml                  up -d market_selection

Notities:
- De service draait in een python:3.12-slim container en installeert runtime dependencies (pyarrow, prometheus_client, orjson, pyyaml).
- Poort 9102 wordt ook op de host gepubliceerd, zodat bestaande Prometheus-scrapes naar 172.18.0.1:9102 blijven werken.
- De service joint het 'monitoring' netwerk; deze definitie komt uit je core compose.
