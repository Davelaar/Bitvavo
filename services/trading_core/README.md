# trading_core — Minimal Trading Loop (Step 5)

Consumes live snapshots from Redis (`ws:ticker:{market}`, `ws:book:{market}`, `ws:trade:{market}`),
reads the active market list from `/srv/trading/common/selection.latest.json`,
computes a conservative buy-only signal, and executes via **paper trading** by default.

Exposes Prometheus metrics on `:9105/metrics`.

## Run locally
```bash
cd services/trading_core
python3 -m venv .venv && . .venv/bin/activate
pip install -r trading_core/requirements.txt
python -m trading_core.main
```

## Systemd
See `trading_core.service`. Update `User=` and paths as needed.
Enable and start:
```bash
sudo cp trading_core.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trading_core
sudo systemctl status trading_core --no-pager
```

## Prometheus
Add a scrape job:
```yaml
- job_name: trading_core
  static_configs:
    - targets: ['127.0.0.1:9105']
```

## Key metrics
- `trading_core_decision_runs_total`
- `trading_core_signals_total{side,reason}`
- `trading_core_orders_total{mode,market,ok}`
- `trading_core_open_positions`

## Config
Edit `trading_core/config.yml` or set `TRADING_CORE_CONFIG` env var.
