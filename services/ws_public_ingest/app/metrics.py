from prometheus_client import Counter, Gauge, Histogram, Summary

events_ingested = Counter("ws_events_ingested_total", "Total WS events ingested", ["channel"])
events_parquet_written = Counter("ws_parquet_rows_total", "Total rows written to Parquet", ["channel"])
ws_connects = Counter("ws_connects_total", "WebSocket connect attempts")
ws_reconnects = Counter("ws_reconnects_total", "WebSocket reconnects")
ws_errors = Counter("ws_errors_total", "WebSocket errors", ["stage"])
subscribe_updates = Counter("ws_subscribe_updates_total", "Subscribe list rebuilds", ["channel"])
