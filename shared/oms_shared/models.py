from __future__ import annotations
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class Side(str, Enum):
    BUY = "1"
    SELL = "2"


class OrdType(str, Enum):
    MARKET = "1"
    LIMIT = "2"


class OrdStatus(str, Enum):
    NEW = "0"
    PARTIALLY_FILLED = "1"
    FILLED = "2"
    CANCELED = "4"
    REJECTED = "8"
    PENDING_NEW = "A"


class ExecType(str, Enum):
    NEW = "0"
    PARTIAL_FILL = "1"
    FILL = "2"
    CANCELED = "4"
    REJECTED = "8"
    PENDING_NEW = "A"


class OrderEvent(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cl_ord_id: str
    account: str
    symbol: str
    side: Side
    ord_type: OrdType
    quantity: Decimal
    price: Optional[Decimal] = None
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class OrderValidatedEvent(OrderEvent):
    pass


class OrderRejectedEvent(BaseModel):
    order_id: str
    cl_ord_id: str
    account: str
    symbol: str
    session_id: str
    reject_reason: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FillEvent(BaseModel):
    exec_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    cl_ord_id: str
    account: str
    symbol: str
    side: Side
    exec_type: ExecType
    last_qty: Decimal
    last_px: Decimal
    cum_qty: Decimal
    leaves_qty: Decimal
    avg_px: Decimal
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class ExecutionReportEvent(FillEvent):
    ord_status: OrdStatus


class MarketDataUpdate(BaseModel):
    symbol: str
    bids: list[tuple[str, str]]  # [(price, qty), ...]
    asks: list[tuple[str, str]]
    last_trade_px: Optional[str] = None
    last_trade_qty: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
