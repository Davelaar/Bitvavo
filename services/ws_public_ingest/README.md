# ws_public_ingest (v1)

Realtime Bitvavo **public** WebSocket ingest — **Python venv-service** volgens projectafspraak.

## TL;DR
```bash
cd /srv/trading/tradingbot/services/ws_public_ingest
cp ws_public_ingest_v1.zip /srv/trading/tradingbot/services/
unzip -o ws_public_ingest_v1.zip -d ws_public_ingest && cd ws_public_ingest

# (1) Configureer config/public.yml indien nodig
# (2) Start service (maakt venv en installeert requirements)
./service.sh
```

### Runtime-eisen
- Redis bereikbaar op `redis:6379` (core network)
- Schrijfrechten naar `/srv/trading/data/parquet`
- Universe/selection bestanden bestaan onder `/srv/trading/common/`

## Auto-sync van markten
- **Ticker**: volgt *universe* uit `universe_eur_trading_excl.jsonl`
- **Trade/Book**: volgt *selection* uit `selection.latest.json` + canary `BTC-EUR`
- De service monitort mtime van universe/selection elke 10s en **herbouwt** de subscribes zonder restart.

## Validatie
1. Logs tonen: `connected`, `subscribed`, `events_ingested_total` > 0
2. Redis streams: `ws:ticker`, `ws:trade`, `ws:book` bevatten records
3. Parquet:
   - `parquet/trades/date=YYYY-MM-DD/market=BTC-EUR/part-*.parquet`
   - bestanden > 0 bytes
4. Metrics: `curl http://localhost:9101/metrics` → counters up

## Stoppen / Updaten
```bash
# stop met ctrl-c als foreground
# of als background via a separate tmux/screen

# update libs
source venv/bin/activate && pip install -r requirements.txt -U
```

## Optioneel: Docker Compose wrapper
Zie `compose/docker-compose.ingest.yml` om deze venv-service via compose te managen (logging/healthcheck).
