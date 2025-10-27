import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ExecResult:
    ok: bool
    order_id: Optional[str]
    filled_price: Optional[float]
    filled_size: Optional[float]
    mode: str
    reason: str

class PaperExecutor:
    def __init__(self, notional_eur: float, tp_pct: float, sl_pct: float):
        self.notional = notional_eur
        self.tp = tp_pct / 100.0
        self.sl = sl_pct / 100.0

    async def place_order(self, market: str, side: str, price: float) -> ExecResult:
        size = self.notional / max(price, 1e-9)
        return ExecResult(True, f"paper-{int(time.time()*1000)}", price, size, "paper", "filled")

class BitvavoExecutor:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    async def place_order(self, market: str, side: str, price: float) -> ExecResult:
        return ExecResult(False, None, None, None, "bitvavo", "not_implemented")
