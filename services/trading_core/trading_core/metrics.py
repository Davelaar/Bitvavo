from prometheus_client import Counter, Gauge

decision_runs_total = Counter("trading_core_decision_runs_total", "Decision loop runs")
signals_total = Counter("trading_core_signals_total", "Signals produced", ["side", "reason"])
orders_total = Counter("trading_core_orders_total", "Orders placed", ["mode", "market", "ok"])
last_run_ts = Gauge("trading_core_last_run_ts", "Unix ts of last run")
open_positions = Gauge("trading_core_open_positions", "Open positions (paper)")
