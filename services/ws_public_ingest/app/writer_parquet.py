import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

class ParquetWriter:
    def __init__(self, root: str):
        self.root = Path(root)

    def _path(self, channel: str, market: str):
        d = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        base = self.root / f"{channel}" / f"date={d}" / f"market={market}"
        base.mkdir(parents=True, exist_ok=True)
        return base / f"part-{int(datetime.now().timestamp())}.parquet"

    def write_rows(self, channel: str, market: str, rows: List[Dict[str, Any]]):
        if not rows:
            return
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, self._path(channel, market))
