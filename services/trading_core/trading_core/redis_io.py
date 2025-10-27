import asyncio, json
from typing import Dict, Any, Optional
import redis.asyncio as redis

class RedisIngest:
    def __init__(self, url: str):
        self.url = url
        self._r: Optional[redis.Redis] = None

    async def connect(self):
        self._r = redis.from_url(self.url, decode_responses=True)
        await self._r.ping()

    async def close(self):
        if self._r:
            await self._r.aclose()

    async def read_latest(self, market: str) -> Dict[str, Any]:
        """
        Flexible reader:
        - Checks keys: ws:{type}:{market} (GET JSON or HGETALL)
        - If streams exist: reads XREVRANGE for latest entry
        """
        assert self._r
        data: Dict[str, Any] = {}
        for kind in ("ticker","book","trade"):
            key = f"ws:{kind}:{market}"
            # GET (JSON)
            v = await self._r.get(key)
            if v:
                try:
                    data[kind] = json.loads(v)
                    continue
                except Exception:
                    pass
            # Hash
            h = await self._r.hgetall(key)
            if h:
                data[kind] = h
                continue
            # Stream (latest)
            xkey = f"{key}:stream"
            try:
                xr = await self._r.xrevrange(xkey, count=1)
                if xr:
                    _, fields = xr[0]
                    data[kind] = dict(fields)
            except Exception:
                pass
        return data
