import asyncio, orjson, logging
import websockets
from websockets.client import WebSocketClientProtocol
from typing import List, Dict, Any, Optional
from .metrics import ws_connects, ws_reconnects, ws_errors, events_ingested

SUB_TPL = {
    "ticker": {"action": "subscribe", "channels": [{"name": "ticker", "markets": []}]},
    "trade":  {"action": "subscribe", "channels": [{"name": "trades", "markets": []}]},
    "book":   {"action": "subscribe", "channels": [{"name": "book", "markets": []}]},
}

class WSClient:
    def __init__(self, url: str, max_retries: int = 3, backoff_ms: int = 750):
        self.url = url
        self.max_retries = max_retries
        self.backoff_ms = backoff_ms
        self.ws: Optional[WebSocketClientProtocol] = None

    async def connect(self):
        ws_connects.inc()
        self.ws = await websockets.connect(self.url, ping_interval=20, ping_timeout=20, close_timeout=5)

    async def close(self):
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

    async def subscribe(self, channels: Dict[str, List[str]]):
        # channels: {"ticker": [...], "trade": [...], "book": [...]}
        for ch, markets in channels.items():
            if not markets:
                continue
            # batch markets to avoid oversized subscribe payloads
            name = SUB_TPL[ch]["channels"][0]["name"]
            BATCH = 50
            for i in range(0, len(markets), BATCH):
                chunk = markets[i:i+BATCH]
                msg = SUB_TPL[ch].copy()
                msg["channels"] = [{"name": name, "markets": chunk}]
                await self.ws.send(orjson.dumps(msg).decode())
                await asyncio.sleep(0.05)

    async def run(self, channels: Dict[str, List[str]], handlers: Dict[str, Any]):
        attempt = 0
        while True:
            try:
                await self.connect()
                await self.subscribe(channels)
                async for raw in self.ws:
                    evt = None
                    try:
                        evt = orjson.loads(raw)
                        if not isinstance(evt, dict):
                            continue
                    except Exception:
                        ws_errors.labels("decode").inc()
                        continue

                    # Classification strictly per project WS-contract
                    evname = evt.get("event")
                    ch = None
                    # ticker events (project uses event="ticker" and bestBid/bestAsk/lastPrice)
                    if evname in ("ticker", "ticker24h") or (
                        "market" in evt and (("bestBid" in evt or "bestAsk" in evt or "lastPrice" in evt) and evname is None)
                    ):
                        ch = "ticker"
                    # trade events
                    elif evname in ("trades", "trade") or (
                        "market" in evt and "amount" in evt and "price" in evt and "side" in evt
                    ):
                        ch = "trade"
                    # book events
                    elif evname == "book" or ("market" in evt and ("bids" in evt or "asks" in evt)):
                        ch = "book"

                    if ch and ch in handlers:
                        try:
                            await handlers[ch](evt)
                            events_ingested.labels(ch).inc()
                        except Exception:
                            ws_errors.labels("handler").inc()
            except Exception:
                ws_errors.labels("loop").inc()
                attempt += 1
                if attempt > self.max_retries:
                    logging.exception("WS failed permanently")
                    await asyncio.sleep(2.0)
                    attempt = 0
                else:
                    ws_reconnects.inc()
                    await asyncio.sleep(self.backoff_ms/1000 * attempt)
            finally:
                await self.close()
