from __future__ import annotations
import os
import json
from decimal import Decimal
from oms_shared.models import OrderEvent, Side
from position_cache import get_position, get_last_trade_price
import structlog

log = structlog.get_logger()

# Instrument config: loaded from env or file; keyed by symbol
# Format: {"AAPL": {"max_order_size": "10000", "position_limit": "50000", "min_price": "0.01", "max_price": "99999"}}
_INSTRUMENTS: dict[str, dict] = {}

COLLAR_PCT = Decimal(os.getenv("PRICE_COLLAR_PCT", "0.10"))  # 10%


def load_instruments(path: str = "/app/config/instruments.json") -> None:
    global _INSTRUMENTS
    try:
        with open(path) as f:
            _INSTRUMENTS = json.load(f)
        log.info("risk.instruments.loaded", count=len(_INSTRUMENTS))
    except FileNotFoundError:
        log.warning("risk.instruments.file_missing", path=path)
        _INSTRUMENTS = _default_instruments()


def _default_instruments() -> dict:
    symbols = ["AAPL", "MSFT", "GOOG", "TSLA", "AMZN"]
    return {
        s: {"max_order_size": "10000", "position_limit": "100000", "min_price": "0.01", "max_price": "99999.99"}
        for s in symbols
    }


def check(order: OrderEvent) -> tuple[bool, str]:
    """Returns (passed, reject_reason). reject_reason is empty string on pass."""
    instr = _INSTRUMENTS.get(order.symbol)
    if instr is None:
        return False, f"Unknown instrument: {order.symbol}"

    # 1. Order size
    max_size = Decimal(instr["max_order_size"])
    if order.quantity > max_size:
        return False, f"Order qty {order.quantity} exceeds max {max_size}"

    # 2. Price collar (limit orders only)
    if order.price is not None:
        last_px = get_last_trade_price(order.symbol)
        if last_px is not None:
            lower = last_px * (1 - COLLAR_PCT)
            upper = last_px * (1 + COLLAR_PCT)
            if not (lower <= order.price <= upper):
                return False, f"Price {order.price} outside collar [{lower:.4f}, {upper:.4f}]"
        # Absolute price bounds
        if order.price < Decimal(instr["min_price"]) or order.price > Decimal(instr["max_price"]):
            return False, f"Price {order.price} outside instrument bounds"

    # 3. Net position limit
    current = get_position(order.account, order.symbol)
    sign = Decimal("1") if order.side == Side.BUY else Decimal("-1")
    projected = current + sign * order.quantity
    limit = Decimal(instr["position_limit"])
    if abs(projected) > limit:
        return False, f"Position limit breach: projected={projected}, limit={limit}"

    return True, ""
