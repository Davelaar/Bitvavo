
# Tradingbot — Technische Blueprint (v1.0)

> Project: Tradingbot Data verzameling  
> Doel: dagtotaal **+5% netto**; bij **-2% dagverlies** → **1 uur pauzeren**.  
> Startkapitaal: **€100**; **max 100%** daginzet; **compounding**.  
> Exclude: **alle stables en fiat** bij het bouwen van het universum.  
> Exchange: **Bitvavo** (REST + WebSocket).  
> Infra: **Ubuntu 24.04**, Docker, Redis, TimescaleDB, ClickHouse, Loki, Prometheus, Grafana, Caddy.

---

## 1. Functionele doelen & regels

### 1.1 Dagdoel en pauze-regel
- **Dagtotaal target:** +5% netto (na fees, slippage).
- **Pauze:** wanneer **NetPNL_day <= -2.00%** → **suspend trading for 60 minutes**; daarna automatisch hervatten.
- **Doorhandelen:** zolang NetPNL_day > -2% blijft en bot niet gepauzeerd is.
- **Tradingvenster:** 24h rollend per exchange-server tijd (UTC).

### 1.2 Budget en compounding
- **Dagelijkse inzetlimiet:** `max_daily_allocation = balance_start_of_day` (100%).
- **Per trade allocatie:** adaptief (zie §4.3); kan splitsen over **meerdere simultane trades**.
- **Compounding:** winst verhoogt `balance_start_of_day_next` via settlement.

### 1.3 Strategie-aanpassing door AI/PNL
- **Strategy Controller** monitort PNL en performance-KPI’s; schakelt tussen **Alpha modes** (bijv. momentum, mean-reversion micro, liquidity-taker) en **Risk modes** (normal, cautious, halt).

---

## 2. Systeemarchitectuur (hoog niveau)

```
[Caddy] ─→ [/grafana] [/] ─→ Filestash
               │
               └──→ Prometheus ─→ Loki
                                   ▲
                                   │
[Bitvavo WS/REST] → Ingestor → Redis Streams → Selector → Signal Engine → Executor → Exchange
                                            └→ Journaler → TimescaleDB + ClickHouse
                                            └→ Metrics Exporters → Prometheus → Grafana
```

### 2.1 Services (Docker containers)
- `trader-bitvavo-ingestor` — live orderbook, tickers, trades.  
- `trader-universe-selector` — bouwt **universum** (alle markten zonder stables/fiat), filtert liquiditeit en spread, kiest **pair**-kandidaten.  
- `trader-signal-engine` — features, alpha, regime-detectie; geeft **intenties** (`BUY`, `SELL`, `HOLD`).  
- `trader-executor` — orderplaatsing, smart pricing, slippage-bescherming, partial fills.  
- `trader-pnl-orchestrator` — rekent realtime PNL (per trade, per pair, dagtotaal), bewaakt **pauze-regel**.  
- `trader-journaler` — persist trade lifecycle en candles → **TimescaleDB** (timeseries) & **ClickHouse** (snelle rapportage).  
- `trader-metrics` — Prometheus exporters (per service).  
- `trader-admin-cli` — eenmalige tools: key-seeding, backfill, sanity checks.

**Message bus:** Redis Streams.  
**Config:** `.env` + YAML per service (mounted configmap).

---

## 3. Externe integratie: Bitvavo

### 3.1 Authenticatie en rate limits
- **API keys** via `.env` → `BITVAVO_API_KEY`, `BITVAVO_API_SECRET` (nooit loggen).  
- **REST** backoff en jitter; **WS** met ping/pong keepalive en auto-reconnect met jitter.

### 3.2 Datastromen
- **Public WS:** `ticker24h`, `trades`, `book` (levels=100 of best bid/ask).  
- **Private WS:** `account`, `orders`, `fills` (voor execution feedback).  
- **REST fallback:** markt-lijsten, plaats/annuleer order, balans, fee-tier.

### 3.3 Universum bouw
- Source: `GET /markets` (REST).  
- **Exclusie-regels:** symbol bevat `EUR`, `USD`, `USDT`, `USDC`, `BUSD`, `DAI`, `TUSD`, `FDUSD`, `EURT` **als quote** → uitsluiten.  
- **Criteria:**  
  - 24h volume ≥ min_volume (default: €25k)  
  - min spread ≤ 0.35%  
  - min ticks in laatste 5 minuten ≥ 50  
  - prijs > €0.0000001 (ontwijk dust).  
- Output: **`/streams/universe.candidates`** (Redis Stream).

---

## 4. Tradinglogica

### 4.1 Feature set (minimaal)
- Midprice, microprice, spread, imbalance (L1/L2), short-term volatility (pMAE/pMFE), trade intensity, buy/sell pressure, microtrend (EMA(3/9)), range compression, VWAP drift, RSI(7) op 1m-aggregatie.
- Regime flags: trending, mean-reverting, choppy (Hurst proxy via variance ratio).

### 4.2 Signalen → intenties
- **Momentum micro:** koop bij microtrend up + dalende spread + lage adverse selection (last trade aggressor buy).  
- **Mean-reversion micro:** koop bij z-score(midprice, 60s) < -1.2 en liquidity near best.  
- **Exit:** take-profit ladder (basis 0.25–0.8%), time-based exit (T+90s), or stop via structural break (imbalance flip + spread widen).  
- **Risk gates:** reject als verwachtte slippage > threshold, of book depth < min.

### 4.3 Allocatie & simultane trades
- `max_open_trades` = 3 (start).  
- `per_trade_allocation` = `min( balance_available / max_open_trades , max_per_trade_eur )`  
  - `max_per_trade_eur` init: €25; auto-aanpassing via PNL en winrate.  
- `position_sizing_mode`: fixed EUR; later: Kelly-lite (clip 0–5%).

### 4.4 PNL & pauze-state machine

```
States: RUNNING → PAUSED(60m) → RUNNING
Trigger pause: NetPNL_day <= -2.00% (incl. open PnL mark-to-mid)
Resume: timer expiry & NetPNL_day > -2.00%
Guard: on resume, reduce risk mode (half size, wider filters) for 30m
```

### 4.5 Fees & slippage
- Fee model: maker/taker (%) uit Bitvavo tier (default taker 0.25%).  
- Slippage model: expected = price_impact(best_depth, size) + latency drift; **hard cap** per order (reject boven cap).

---

## 5. Datamodellen & events

### 5.1 Redis Streams (kanaalnamen)

| Stream key | Producer | Payload (JSON) |
|---|---|---|
| `streams:universe.candidates` | selector | `{ "ts": <ms>, "pair": "BTC-EUR", "bid": 65000.1, "ask": 65000.9, "spread_bps": 12, "vol24h_eur": 1.2e6 }` |
| `streams:signals` | signal-engine | `{ "ts": <ms>, "pair": "BTC-EUR", "intent": "BUY"|"SELL"|"EXIT", "score": 0.78, "alpha": "mom_micro", "ttl_ms": 120000 }` |
| `streams:orders.new` | executor | `{ "ts": <ms>, "pair": "BTC-EUR", "side": "BUY"|"SELL", "amount": "0.001", "limit": "65000.5", "client_id": "T20251026-0001" }` |
| `streams:orders.fill` | executor | `{ "ts": <ms>, "pair": "BTC-EUR", "order_id": "...", "client_id": "...", "filled": "0.001", "avg_price": "65010.0", "fee": "0.00025 BTC" }` |
| `streams:positions` | pnl-orchestrator | `{ "ts": <ms>, "pair": "BTC-EUR", "position_id": "...", "side": "LONG|FLAT", "qty": "0.001", "entry": "65010.0", "upnl_eur": 1.23 }` |
| `streams:journal` | journaler | normale events voor auditing |

**Consistente veldnamen:** altijd `pair` (enkelvoud), `ts` (epoch ms), `side`, `amount`, `limit` (string).

### 5.2 TimescaleDB schema (kern)
- `candles_1m(pair TEXT, t TIMESTAMPTZ, open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC, vol NUMERIC, PRIMARY KEY(pair,t))` (Hypertable).
- `trades(pair TEXT, t TIMESTAMPTZ, side TEXT, price NUMERIC, qty NUMERIC, fee NUMERIC, client_id TEXT, order_id TEXT)`
- `positions(position_id TEXT, pair TEXT, opened_at TIMESTAMPTZ, closed_at TIMESTAMPTZ NULL, entry NUMERIC, exit NUMERIC NULL, qty NUMERIC, pnl_eur NUMERIC)`
- Indexen op `(pair,t)` en `(opened_at)`.

### 5.3 ClickHouse schema (rapportage)
- `events` MergeTree by (pair, event_date, event_ts) — alle lifecycle events; snelle PnL queries.

---

## 6. Metrics (Prometheus)

**Common labels:** `service`, `pair`  

- `trader_signals_total{alpha, intent}`  
- `trader_orders_submitted_total{result}`  
- `trader_order_latency_ms_bucket` (histogram)  
- `trader_upnl_eur` (gauge per pair)  
- `trader_day_pnl_eur` (gauge)  
- `trader_state{state="RUNNING|PAUSED"}`  
- `trader_risk_mode{mode="normal|cautious|halt"}`  
- `trader_slippage_bps_bucket`  
- `trader_universe_size`

**Alerts (Grafana/Prometheus):**
- Day PNL ≤ -2% → Alert + auto-pause.
- Fill ratio < 30% (10m) → waarschuwing; spread filter aanscherpen.

---

## 7. Configuratie

### 7.1 `.env` (voorbeeld)
```
BITVAVO_API_KEY=
BITVAVO_API_SECRET=
BASE_CURRENCY=EUR
UNIVERSE_MIN_VOL_EUR=25000
UNIVERSE_MAX_SPREAD_BPS=35
MAX_OPEN_TRADES=3
MAX_PER_TRADE_EUR=25
DAY_PAUSE_THRESHOLD_PCT=-2.0
DAY_TARGET_PCT=5.0
```

### 7.2 Service YAML (fragment `signal-engine.yaml`)
```yaml
alpha_modes:
  - name: mom_micro
    enabled: true
    params: { ema_fast: 3, ema_slow: 9, tp_bps: [25, 60, 80], ttl_ms: 90000 }
  - name: meanrev_micro
    enabled: true
    params: { z_window_s: 60, z_entry: -1.2, tp_bps: [20, 50], ttl_ms: 120000 }
risk:
  spread_bps_max: 35
  slippage_bps_cap: 20
  min_book_depth_eur: 500
```

---

## 8. Trade lifecycle

1. **Select pair** (selector) → `streams:universe.candidates`.  
2. **Signal** (signal-engine) → `streams:signals`.  
3. **Validate & place** (executor) → Bitvavo order (limit IOC of post-only per alpha).  
4. **Monitor fills** (private WS) → `streams:orders.fill`.  
5. **Manage position** (executor + pnl-orchestrator): TP ladder, time exit, break exit.  
6. **Journal** (journaler) → DB + ClickHouse.  
7. **PNL update** → `trader_day_pnl_eur`; **pause** indien ≤ -2%.

---

## 9. Schaalbaarheid & fouttolerantie

- **Idempotente consumers** op Redis Streams (consumergroups, `XREADGROUP`).  
- **Backpressure:** bounded queues, drop oldest non-critical.  
- **Reconnect** met backoff (WS/REST).  
- **Circuit breakers** rond REST orderplaatsing.  
- **At-least-once** journal; dedupe via `client_id`.  
- **Hot-reload config** via SIGHUP of configmap watch.

---

## 10. Deployment plan (geen code uitrollen nu)

1. **Secrets**: voeg Bitvavo keys aan `/srv/trading/secrets/.env.trader`.  
2. **Compose uitbreiding**: nieuwe services zoals hierboven; mount config + secrets.  
3. **DB init**: run init-scripts voor Timescale en ClickHouse.  
4. **Smoke tests**: dry-run modus (executor sim mode).  
5. **Go-live**: echte orders met klein size (bijv. €5), live PNL validatie.  
6. **Ramp-up**: vergroot `MAX_PER_TRADE_EUR` en `MAX_OPEN_TRADES` via PNL-controller.

---

## 11. Beheer & runbook

- **Start/stop**: `docker compose up -d trader-*` / `... down`.  
- **Logs**: Loki querie: `{service="trader-*"}`.  
- **Metrics**: Grafana dashboard `Trader Overview`.  
- **Dag reset**: 00:00 UTC snapshot van PNL, nieuwe `balance_start_of_day`.  
- **Incident**: state → `halt`, executor cancelt open orders; resume via CLI of timer.

---

## 12. Security & betrouwbaarheid (ChatGPT/automation)

- **Declaratieve scripts** (idempotent), met preflight checks (`assert_cmd`, `assert_env`).  
- **Checksums** voor ZIP-deploys; versie in `VERSION`-file.  
- **Dry-run** modus voor executor.  
- **Explicit allowlist** voor pair-namen en ordertypes.  
- **No key logging**; secrets in bind-mount `/srv/trading/secrets`.  
- **Role separation**: executor heeft alleen wat nodig is; geen DB write recht buiten journaler.

---

## 13. Naming & consistentie

- `pair` (enkelvoud) in alle events/datasets.  
- Timestamps als `ts` (int64 ms).  
- Geldbedragen in **EUR** tenzij anders vermeld.  
- BPS = basispunten (1 bps = 0.01%).

---

## 14. Deliverables (volgende stap)

- **ZIP #2 — trading-services**: 
  - Compose services `trader-*`  
  - Config YAML’s  
  - Prometheus exporters  
  - DB init SQL (Timescale & ClickHouse)  
  - Admin CLI + README (start in sim, dan live)  

Na jouw “GO” lever ik ZIP #2 waarmee je direct **LIVE** kunt draaien (eerst sim-flag).

---

## 15. Appendix — Prometheus targets (samenvatting)
- `prometheus:9090` → `/prometheus/metrics`
- `grafana:3000` → `/grafana/metrics`
- `loki:3100` → `/metrics`
