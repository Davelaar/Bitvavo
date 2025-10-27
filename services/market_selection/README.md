# Step 4 — market_selection (venv-service)

## 0) Git-validatie
```bash
cd /srv/trading/tradingbot
git status
git remote -v
git pull --ff-only
```

## 1) Uitpakken vanaf /srv/trading/upload
```bash
mkdir -p /srv/trading/tradingbot/services
cd /srv/trading/tradingbot/services
unzip -o /srv/trading/upload/market_selection_step4_v1.zip -d market_selection
```

## 2) Config controleren
- inputs.universe_file: /srv/trading/common/universe_eur_trading_excl.jsonl
- inputs.parquet_tickers_root: /srv/trading/data/parquet/tickers
- output.selection_file: /srv/trading/common/selection.latest.json

## 3) Start
```bash
cd /srv/trading/tradingbot/services/market_selection
./service.sh
```

## 4) Validatie
```bash
cat /srv/trading/common/selection.latest.json
curl -s http://localhost:9102/metrics | egrep 'selection_size|markets_considered|markets_eligible|run_success_total' || true
```

## 5) Afsluiten (commit/push/ci/deploy)
```bash
cd /srv/trading/tradingbot
git add -A
git commit -m "feat: stap 4 – market_selection toegevoegd"
git push origin main
LE_EMAIL="r.davelaar@icloud.com" DOMAIN="snapdiscounts.nl" make ci
# optioneel
make deploy
make status
```
## Market Selection – BBO reconstructie

- Rekonstrueert bestBid en bestAsk uit losse ticker-updates (strings) binnen het recente venster.
- Neemt per kant de laatst geziene waarde; berekent spread in bps wanneer beide aanwezig zijn.
- Geen wijzigingen aan config/metrics; respecteert require_bid_ask en max_spread_bps.

