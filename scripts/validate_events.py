#!/usr/bin/env python3
import json, glob, sys
from jsonschema import Draft202012Validator

SCHEMA_MAP = {
    "streams_universe_candidates": "streams.universe.candidates",
    "streams_signals": "streams.signals",
    "streams_orders_new": "streams.orders.new",
    "streams_orders_fill": "streams.orders.fill",
}

def load_schema(key):
    with open(f"schemas/{key}.schema.json") as f:
        return json.load(f)

OK = True
for path in glob.glob("ci/samples/**/*.json", recursive=True):
    folder = path.split('/')[-2]
    key = SCHEMA_MAP.get(folder)
    if not key:
        print(f"[SKIP] {path} (no schema mapping)")
        continue
    schema = load_schema(key)
    data = json.load(open(path))
    v = Draft202012Validator(schema)
    errs = sorted(v.iter_errors(data), key=lambda e: e.path)
    if errs:
        OK = False
        print(f"[FAIL] {path}")
        for e in errs: print("  -", e.message)
    else:
        print(f"[OK]   {path}")

sys.exit(0 if OK else 1)
