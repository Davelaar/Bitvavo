import os, time, logging, argparse, json, orjson
from pathlib import Path
from typing import Dict, List, Tuple
import yaml
import pyarrow.parquet as pq
from prometheus_client import start_http_server, Counter, Gauge

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
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[:max_files]


def scan_market(paths):
    """
    Lees elk Parquet-part afzonderlijk, normaliseer dictionary<str> -> str
    en tel total_rows correct door.
    """
    import pyarrow as pa, pyarrow.parquet as pq, pyarrow.types as pat
    total_rows = 0
    last_bid = None
    last_ask = None
    has_bid = False
    has_ask = False
    for pth in paths:
        tbl = None
        # 1) Probeer direct
        try:
            tbl = pq.read_table(pth)
        except Exception:
            pass
        # 2) Indien nog niet gelukt, lees per row-group
        if tbl is None:
            try:
                pf = pq.ParquetFile(pth)
                parts = []
                for i in range(pf.num_row_groups):
                    t = pf.read_row_group(i)
                    # cast 'market' indien dictionary geencodeerd
                    if 'market' in t.column_names:
                        col = t['market']
                        if pat.is_dictionary(col.type):
                            t = t.set_column(t.column_names.index('market'),
                                             'market',
                                             col.cast(pa.string()))
                    parts.append(t)
                if parts:
                    tbl = pa.concat_tables(parts, promote=True)
            except Exception:
                pass
        # 3) Laatste poging: opnieuw lezen en enkel 'market' naar string casten
        if tbl is None:
            try:
                tbl = pq.read_table(pth)
                if 'market' in tbl.column_names:
                    col = tbl['market']
                    if pat.is_dictionary(col.type):
                        import pyarrow as pa
                        tbl = tbl.set_column(tbl.column_names.index('market'),
                                             'market',
                                             col.cast(pa.string()))
            except Exception:
                continue

        total_rows += tbl.num_rows
        cols = set(tbl.column_names)
        for c in ["bestBid","bid","lastBid","best_bid"]:
            if c in cols and tbl.num_rows:
                last_bid = tbl[c][-1].as_py()
                has_bid = True
                break
        for c in ["bestAsk","ask","lastAsk","best_ask"]:
            if c in cols and tbl.num_rows:
                last_ask = tbl[c][-1].as_py()
                has_ask = True
                break
    spread_bps = None
    if has_bid and has_ask:
        try:
            bid = float(last_bid); ask = float(last_ask)
            mid = (bid + ask)/2 if (bid != 0 and ask != 0) else None
            if mid:
                spread_bps = (ask - bid)/mid * 10000.0
        except Exception:
            pass
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
