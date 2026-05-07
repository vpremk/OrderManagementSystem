from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Text, BigInteger
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SettlementConfig(Base):
    """Key/value store for one-time bootstrap values (e.g. Circle wallet set ID)."""
    __tablename__ = "settlement_config"

    key       = Column(String(64), primary_key=True)
    value     = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SettlementAccount(Base):
    """Maps an OMS account to a Circle W3S MSCA wallet."""
    __tablename__ = "settlement_accounts"

    account          = Column(String(64), primary_key=True)
    circle_wallet_id = Column(String(128), nullable=False)
    wallet_address   = Column(String(42), nullable=False)   # on-chain 0x address
    blockchain       = Column(String(32), nullable=False, default="ETH-SEPOLIA")
    created_at       = Column(DateTime, default=datetime.utcnow)


class Settlement(Base):
    __tablename__ = "settlements"

    settlement_id      = Column(String(36), primary_key=True,
                                default=lambda: str(uuid.uuid4()))
    trade_id           = Column(String(36), nullable=False, unique=True)
    buy_order_id       = Column(String(36), nullable=False)
    sell_order_id      = Column(String(36), nullable=False)
    buy_exec_id        = Column(String(36), nullable=False)
    sell_exec_id       = Column(String(36), nullable=False)
    buy_account        = Column(String(64), nullable=False)
    sell_account       = Column(String(64), nullable=False)
    symbol             = Column(String(16), nullable=False)
    quantity           = Column(Numeric(20, 8), nullable=False)
    price              = Column(Numeric(20, 8), nullable=False)
    notional_usd       = Column(Numeric(20, 8), nullable=False)
    # Circle W3S fields
    circle_transfer_id = Column(String(128), nullable=True)
    tx_hash            = Column(String(66), nullable=True)
    block_height       = Column(BigInteger, nullable=True)
    network_fee        = Column(String(32), nullable=True)
    blockchain         = Column(String(32), nullable=True)
    # Status lifecycle: PENDING → PROCESSING → SETTLED | FAILED
    status             = Column(String(20), nullable=False, default="PENDING")
    settled_at         = Column(DateTime, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
    error_msg          = Column(Text, nullable=True)
