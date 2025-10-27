import asyncio, json, os, time, logging, yaml
from pathlib import Path
from typing import Dict, Any
from prometheus_client import start_http_server
from trading_core.redis_io import RedisIngest
from trading_core.decision import compute_signal, Decision
from trading_core.executor import PaperExecutor, BitvavoExecutor
from trading_core.metrics import decision_runs_total, signals_total, orders_total, last_run_ts, open_positions

logging.basicConfig(level=os.environ.get("LOGLEVEL","INFO"))
log = logging.getLogger("trading_core")

def load_cfg(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_selection(path: str):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        log.warning("No selection file yet: %s", e)
        return []

class Cooldown:
    def __init__(self, seconds: int):
        self.seconds = seconds
        self._last = {}

    def hit(self, market: str) -> bool:
        t = self._last.get(market, 0)
        return time.time() - t < self.seconds

    def set(self, market: str):
        self._last[market] = time.time()

async def run(cfg_path: str):
    cfg = load_cfg(cfg_path)
    start_http_server(cfg["http"]["port"], addr=cfg["http"]["host"])
    log.info("Metrics HTTP on %s:%s", cfg["http"]["host"], cfg["http"]["port"])

    ri = RedisIngest(cfg["redis_url"])
    await ri.connect()

    selection_file = cfg["selection_file"]
    exec_mode = cfg["execution"]["mode"]
    notional = float(cfg["risk"]["notional_per_trade_eur"])
    tp = float(cfg["risk"]["take_profit_pct"])
    sl = float(cfg["risk"]["stop_loss_pct"])
    cooldown = Cooldown(int(cfg["signals"]["cooldown_s"]))

    if exec_mode == "paper":
        executor = PaperExecutor(notional, tp, sl)
    else:
        executor = BitvavoExecutor(cfg["execution"]["bitvavo"])

    max_positions = int(cfg["risk"]["max_open_positions"])
    positions = {}

    poll_sleep = cfg.get("poll_interval_ms", 500)/1000.0

    while True:
        decision_runs_total.inc()
        last_run_ts.set(time.time())

        selection = load_selection(selection_file)
        markets = [m if isinstance(m, str) else m.get("market") for m in selection]
        markets = [m for m in markets if m]

        open_positions.set(len(positions))

        for market in markets:
            if market in positions and len(positions) >= max_positions:
                continue

            snapshot = await ri.read_latest(market)
            d: Decision = compute_signal(market, snapshot, {
                "max_spread_bps": cfg["signals"]["max_spread_bps"],
                "min_book_depth_eur": cfg["signals"]["min_book_depth_eur"],
            })

            if not d.side:
                continue

            if cooldown.hit(market):
                continue

            signals_total.labels(side=d.side, reason=d.reason).inc()

            res = await executor.place_order(market, d.side, d.price or 0.0)
            orders_total.labels(mode=exec_mode, market=market, ok=str(res.ok)).inc()

            if res.ok and d.side == "buy":
                positions[market] = {"entry_price": res.filled_price, "size": res.filled_size}
                cooldown.set(market)
                open_positions.set(len(positions))

        await asyncio.sleep(poll_sleep)

def main():
    cfg_path = os.environ.get("TRADING_CORE_CONFIG", str(Path(__file__).with_name("config.yml")))
    try:
        asyncio.run(run(cfg_path))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
