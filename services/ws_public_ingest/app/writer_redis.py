import asyncio, orjson, time
from typing import Dict, Any
import redis.asyncio as redis

class RedisWriter:
    def __init__(self, dsn: str):
        self._client = redis.from_url(dsn, decode_responses=False)
    async def write_stream(self, stream: str, payload: Dict[str, Any]):
        data = orjson.dumps(payload)
        await self._client.xadd(stream, {"v": data})
    async def ping(self):
        await self._client.ping()
