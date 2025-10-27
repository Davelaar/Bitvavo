# ✅ Tradingbot – Uitvoering Checklist

## 0️⃣ Pre-flight
- [ ] Serverstack draait (`docker ps` → grafana, prometheus, redis, timescale, loki)
- [ ] SSH key-only login, UFW 22/80/443 open, TLS actief
- [ ] Grafana bereikbaar → [https://snapdiscounts.nl/grafana](https://snapdiscounts.nl/grafana)

## 0b️⃣ Git-check
- [ ] `cd /srv/trading/tradingbot`
- [ ] `git status` → clean op branch **main**
- [ ] `git remote -v` → `git@github.com:Davelaar/Bitvavo.git`
- [ ] `git pull --ff-only`
- [ ] `.gitignore` bevat `grafana/`
- [ ] Geen runtime-mappen in repo

## 1️⃣ Universe & Baselines
- [ ] `/srv/trading/common/market_spec_v1.jsonl`
- [ ] `/srv/trading/common/universe_eur_trading_excl.jsonl`
- [ ] `/srv/trading/common/baseline_v1.latest.jsonl`
- [ ] Geen `null` waarden, aantal regels = universe

## 2️⃣ Core Stack – Validatie
- [ ] Container `grafana` draait onder core stack
- [ ] Data in `/srv/trading/grafana/`  
- [ ] Provisioning in `/srv/trading/grafana/provisioning/`
- [ ] Repo bevat hooguit losse export `dashboard.json`

## 3️⃣ Service 1 – ws_public_ingest
- [ ] Config `/srv/trading/config/ws_ingest/public.yml`
- [ ] Subscribes: ticker / trade / book
- [ ] Output → Redis Streams + Parquet + Metrics
- [ ] Logs OK, Parquet rolt, Prometheus target “up”

## 4️⃣ Service 2 – market_selection
- [ ] Shortlist 6–18 paren, guards gevuld
- [ ] Output `/srv/trading/common/selection.latest.json`
- [ ] Symbolen ⊆ universe

## 5️⃣ Service 3 – features_signals
- [ ] Features per paar < 60 s oud
- [ ] Output → Redis `feat:*` + Parquet `features/`
- [ ] Geen nulls in kernfeatures

## 6️⃣ Service 4 – ai_decider
- [ ] FastAPI `/decide` < 200 ms
- [ ] BUY / SELL / HOLD + explain-tag
- [ ] Output → Redis `order:intent`

## 7️⃣ Service 5 – risk_policy_gate
- [ ] Guards: loss-streak, cooldown, slippage, min-size, fee-tier
- [ ] Reject-redenen duidelijk
- [ ] Prometheus-metrics per guard zichtbaar

## 8️⃣ Service 6 – order_executor
- [ ] PAPER-mode succesvol end-to-end
- [ ] LIVE proeforder (klein limit BTC-EUR) geplaatst / geannuleerd
- [ ] Pas daarna `LIVE=1`

## 9️⃣ Service 7 – position_manager
- [ ] Posities live in Redis
- [ ] Persist in Parquet / Timescale
- [ ] PnL ≈ journal (< 0.1 %)

## 🔟 Service 8 – journal_metrics
- [ ] Logs → Loki, journal → Parquet / Timescale
- [ ] Prometheus-metrics: `orders_total`, `decision_latency`, …
- [ ] Dashboards vullen, flows traceerbaar via sessie-ID

## 11️⃣ Monitoring & Alerts
- [ ] Grafana-dashboards: ingest health, selection quality, execution SLA, PnL curve
- [ ] Alerts: ingest stalled, order timeouts, loss-streak guard activations
- [ ] Back-ups: `/srv/trading/backups/stack-<timestamp>.tar.gz`

---

🟢 **Status:**  
- [x] Core stack draait stabiel  
- [x] Grafana buiten projectmap bevestigd  
- [x] Git-check voltooid  
- [ ] Klaar voor `ws_public_ingest` activering
