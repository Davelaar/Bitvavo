from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Decision:
    market: str
    side: Optional[str]   # 'buy' | 'sell' | None
    reason: str
    price: Optional[float]
    size: Optional[float]

def _to_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default

def compute_signal(market: str, snapshot: Dict[str, Any], params: Dict[str, Any]) -> Decision:
    """
    Naive but safe: micro-spread and top-of-book liquidity gate.
    - Requires book best bids/asks with sizes in quote currency terms (EUR)
    - Buy-only MVP; no shorting.
    """
    book = snapshot.get("book", {}) or {}
    bid = _to_float(book.get("bestBid") or book.get("bid") or book.get("b"), None)
    ask = _to_float(book.get("bestAsk") or book.get("ask") or book.get("a"), None)
    bid_size_eur = _to_float(book.get("bestBidSizeEur") or book.get("bidSizeEur"), None)
    ask_size_eur = _to_float(book.get("bestAskSizeEur") or book.get("askSizeEur"), None)

    if not (bid and ask):
        return Decision(market, None, "no_bbo", None, None)

    spread = (ask - bid) / ((ask + bid) / 2)
    max_spread = (params.get("max_spread_bps", 12)) / 10_000
    min_depth = params.get("min_book_depth_eur", 200)

    if spread > max_spread:
        return Decision(market, None, f"spread_too_wide", None, None)
    if (bid_size_eur is not None and bid_size_eur < min_depth) or (ask_size_eur is not None and ask_size_eur < min_depth):
        return Decision(market, None, "thin_book", None, None)

    ticker = snapshot.get("ticker", {}) or {}
    last_price = _to_float(ticker.get("lastPrice") or ticker.get("price"), (ask+bid)/2)
    price = last_price if last_price else (ask+bid)/2

    return Decision(market, "buy", "tight_spread_liquid_book", price, None)
