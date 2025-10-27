import os, time, logging, argparse, json, orjson
from pathlib import Path
from typing import Dict, List, Tuple
import yaml
import pyarrow.parquet as pq
from prometheus_client import start_http_server, Counter, Gauge

def last_scalar(tbl, name):
    try:
        arr = tbl[name]
    except Exception:
        return None
    chunks = getattr(arr, 'chunks', []) or []
    for ch in reversed(chunks):
        n = len(ch)
        if n == 0 or (hasattr(ch,'null_count') and ch.null_count == n):
            continue
        for i in range(n-1, -1, -1):
            if not ch.is_null(i):
                try:
                    return ch[i].as_py()
                except Exception:
                    return None
    try:
        return arr[-1].as_py()
    except Exception:
        return None

run_success = Counter("selection_run_success_total","Successful selection runs")
markets_considered = Gauge("selection_markets_considered","Markets considered this run")
markets_eligible = Gauge("selection_markets_eligible","Markets eligible after filters")
selection_size_g = Gauge("selection_size","Final selection size")

def load_yaml(p: str) -> Dict:
    with open(p,"r") as f:
        return yaml.safe_load(f)

def read_universe(path: str) -> List[str]:
    out = []
    p = Path(path)
    if not p.exists():
        return out
    with p.open("r") as f:
        for line in f:
            s = line.strip()
            if not s: continue
            if s.startswith("{"):
                try:
                    obj = orjson.loads(s)
                    sym = obj.get("symbol") or obj.get("market") or obj.get("pair")
                    if sym: out.append(sym)
                except Exception:
                    pass
            else:
                out.append(s)
    return out

def latest_market_paths(root: Path, market: str, max_files: int):
    if not root.exists():
        return []
    paths = list(root.glob(f"date=*/market={market}/part-*.parquet"))
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)  # newest → oldest
    return paths[:max_files]




def scan_market(paths):
    """
    Lees parts (nieuw -> oud), tel ALLE rijen in het venster,
    en neem per kant de meest recente waarde; spread na cast.
    """
    import pyarrow.parquet as pq

    def last_non_null_table_col(tbl, col):
        if col not in tbl.column_names:
            return None
        arr = tbl[col].combine_chunks()
        try:
            nn = arr.drop_null()
            if len(nn):
                return nn[len(nn)-1].as_py()
        except Exception:
            pass
        n = len(arr)
        for i in range(n-1, -1, -1):
            v = arr[i].as_py()
            if v is not None:
                return v
        return None

    # 1) tel ALLE rows (zonder vroeg te breken)
    total_rows = 0
    for pth in paths:
        try:
            pf = pq.ParquetFile(pth)
            meta = pf.metadata
            if meta is not None and meta.num_rows is not None:
                total_rows += int(meta.num_rows)
        except Exception:
            continue

    # 2) zoek nieuwste bid/ask (mag vroeg stoppen zodra beide gevonden)
    last_bid = None
    last_ask = None
    for pth in paths:
        try:
            tbl = pq.ParquetFile(pth).read_row_group(0)
        except Exception:
            continue

        if last_bid is None:
            for c in ("bestBid","bid","lastBid","best_bid"):
                v = last_non_null_table_col(tbl, c)
                if v is not None:
                    last_bid = v
                    break

        if last_ask is None:
            for c in ("bestAsk","ask","lastAsk","best_ask"):
                v = last_non_null_table_col(tbl, c)
                if v is not None:
                    last_ask = v
                    break

        if last_bid is not None and last_ask is not None:
            break

    has_bid = last_bid is not None
    has_ask = last_ask is not None
    spread_bps = None
    if has_bid and has_ask:
        try:
            bid = float(last_bid); ask = float(last_ask)
            if bid > 0 and ask > 0:
                mid = (bid + ask)/2.0
                spread_bps = (ask - bid)/mid * 10000.0
        except Exception:
            spread_bps = None

    return {"rows": total_rows, "has_bid": has_bid, "has_ask": has_ask, "spread_bps": spread_bps}
def choose_markets(universe, tick_root: Path, cfg: Dict):
    max_files = int(cfg["inputs"]["max_files_per_market"])
    min_rows = int(cfg["inputs"]["min_rows_per_market"])
    max_spread = float(cfg["selection"]["max_spread_bps"])
    target = int(cfg["selection"]["target_size"])
    require_ba = bool(cfg["selection"]["require_bid_ask"])
    always = list(cfg["selection"]["always_include"] or [])
    exclude = set(cfg["selection"]["exclude_markets"] or [])

    considered = 0
    scored = []  # (spread_bps, -rows, market)
    for m in universe:
        if m in exclude:
            continue
        paths = latest_market_paths(tick_root, m, max_files)
        if not paths:
            continue
        considered += 1
        stat = scan_market(paths)
        if stat["rows"] < min_rows:
            continue
        if require_ba and not (stat["has_bid"] and stat["has_ask"]):
            continue
        if stat["spread_bps"] is None or stat["spread_bps"] > max_spread:
            continue
        scored.append((stat["spread_bps"], -stat["rows"], m))

    markets_considered.set(considered)
    markets_eligible.set(len(scored))
    scored.sort(key=lambda x: (x[0], x[1]))
    sel = [m for _,__,m in scored]

    out = []
    for a in always:
        if a in universe and a not in out:
            out.append(a)
    for m in sel:
        if m not in out:
            out.append(m)
        if len(out) >= target:
            break
    selection_size_g.set(len(out))
    return out

def write_selection(path: str, markets: List[str]):
    data = {"markets": markets}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",",":"))
    os.replace(tmp, path)

def run_once(cfg: Dict):
    uni = read_universe(cfg["inputs"]["universe_file"])
    tick_root = Path(cfg["inputs"]["parquet_tickers_root"])
    sel = choose_markets(uni, tick_root, cfg)
    write_selection(cfg["output"]["selection_file"], sel)
    run_success.inc()
    logging.info("selection written size=%d file=%s", len(sel), cfg["output"]["selection_file"])

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    logging.basicConfig(level=getattr(logging, cfg["runtime"]["log_level"].upper(), logging.INFO),
                        format='%(asctime)s %(levelname)s %(message)s')
    start_http_server(int(cfg["runtime"]["metrics_port"]))
    interval = int(cfg["runtime"]["interval_seconds"])
    while True:
        try:
            run_once(cfg)
        except Exception:
            logging.exception("selection run failed")
        time.sleep(interval)

if __name__ == "__main__":
    main()
