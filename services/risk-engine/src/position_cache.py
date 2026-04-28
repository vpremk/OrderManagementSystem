from __future__ import annotations
import os
from decimal import Decimal
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def get_position(account: str, symbol: str) -> Decimal:
    key = f"pos:{account}:{symbol}"
    val = _get_client().get(key)
    return Decimal(val) if val else Decimal("0")


def get_last_trade_price(symbol: str) -> Decimal | None:
    key = f"last_px:{symbol}"
    val = _get_client().get(key)
    return Decimal(val) if val else None


def set_last_trade_price(symbol: str, price: Decimal) -> None:
    _get_client().set(f"last_px:{symbol}", str(price))


def update_position(account: str, symbol: str, delta: Decimal) -> Decimal:
    key = f"pos:{account}:{symbol}"
    new_val = _get_client().incrbyfloat(key, float(delta))
    return Decimal(str(new_val))
