import asyncio, logging, argparse, time, os, json, orjson
from pathlib import Path
from typing import Dict, List, Any
import yaml
from prometheus_client import start_http_server
from .writer_redis import RedisWriter
from .writer_parquet import ParquetWriter
from .ws_client import WSClient
from .metrics import events_parquet_written, subscribe_updates

def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def read_lines_file(path: str) -> List[str]:
    lines = []
    with open(path, "r") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            # handle jsonl or plain symbols per line
            if s.startswith("{"):
                try:
                    obj = orjson.loads(s)
                    sym = obj.get("symbol") or obj.get("market") or obj.get("pair")
                    if sym:
                        lines.append(sym)
                except:
                    pass
            else:
                lines.append(s)
    return lines

def load_selection(path: str) -> List[str]:
    try:
        with open(path, "r") as f:
            data = json.load(f)
        # supports either {"markets": [...]} or a plain list
        if isinstance(data, dict):
            return list(data.get("markets") or data.get("symbols") or [])
        elif isinstance(data, list):
            return [str(x) for x in data]
    except FileNotFoundError:
        return []
    return []

def build_subscribe_lists(cfg: Dict[str, Any]) -> Dict[str, List[str]]:
    rt = cfg["runtime"]
    subs = cfg["subscribe"]
    universe = []
    selection = []

    uni_path = rt["universe_file"]
    sel_path = rt["selection_file"]

    if Path(uni_path).exists():
        universe = read_lines_file(uni_path)
    if Path(sel_path).exists():
        selection = load_selection(sel_path)

    def choose(mode: str, fallback: List[str]) -> List[str]:
        if mode == "universe":
            return universe
        if mode == "selection":
            out = list(selection)
            for x in fallback:
                if x not in out:
                    out.append(x)
            return out
        return fallback

    out = {}
    out["ticker"] = choose(subs["ticker"]["mode"], subs["ticker"]["list"] or [])
    out["trade"]  = choose(subs["trade"]["mode"],  subs["trade"]["list"] or [])
    out["book"]   = choose(subs["book"]["mode"],   subs["book"]["list"] or [])
    return out

async def main_async(cfg_path: str):
    cfg = load_yaml(cfg_path)
    logging.basicConfig(level=getattr(logging, cfg["runtime"]["log_level"].upper(), logging.INFO),
                        format='%(asctime)s %(levelname)s %(message)s')

    start_http_server(int(cfg["runtime"]["metrics_port"]))

    redisw = RedisWriter(cfg["runtime"]["redis_dsn"])
    parquetw = ParquetWriter(cfg["runtime"]["parquet_root"])

    subs = build_subscribe_lists(cfg)
    ws = WSClient(cfg["ws"]["url"], cfg["ws"]["max_retries"], cfg["ws"]["base_backoff_ms"])

    async def handle_ticker(evt):
        market = evt.get("market") or evt.get("symbol") or "UNKNOWN"
        await redisw.write_stream("ws:ticker", evt)
        parquetw.write_rows("tickers", market, [evt])
        events_parquet_written.labels("ticker").inc()

    async def handle_trade(evt):
        market = evt.get("market") or "UNKNOWN"
        await redisw.write_stream("ws:trade", evt)
        parquetw.write_rows("trades", market, [evt])
        events_parquet_written.labels("trade").inc()

    async def handle_book(evt):
        market = evt.get("market") or "UNKNOWN"
        await redisw.write_stream("ws:book", evt)
        parquetw.write_rows("books", market, [evt])
        events_parquet_written.labels("book").inc()

    handlers = {"ticker": handle_ticker, "trade": handle_trade, "book": handle_book}

    async def autosync_task():
        # Rebuild subscription lists when universe/selection mtime changes
        rt = cfg["runtime"]
        uni = Path(rt["universe_file"])
        sel = Path(rt["selection_file"])
        prev = (uni.stat().st_mtime if uni.exists() else 0, sel.stat().st_mtime if sel.exists() else 0)
        while True:
            await asyncio.sleep(10)
            now = (uni.stat().st_mtime if uni.exists() else 0, sel.stat().st_mtime if sel.exists() else 0)
            if now != prev:
                prev = now
                new_subs = build_subscribe_lists(cfg)
                subscribe_updates.labels("ticker").inc()
                subscribe_updates.labels("trade").inc()
                subscribe_updates.labels("book").inc()
                # soft-resubscribe: reconnect to apply new markets
                await ws.close()
                await asyncio.sleep(0.5)
                asyncio.create_task(ws.run(new_subs, handlers))

    # launch ws loop and autosync
    asyncio.create_task(ws.run(subs, handlers))
    asyncio.create_task(autosync_task())

    # keep running
    while True:
        await asyncio.sleep(3600)

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    return ap.parse_args()

def main():
    args = parse_args()
    asyncio.run(main_async(args.config))

if __name__ == "__main__":
    main()
