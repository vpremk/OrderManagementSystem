from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, String, Numeric, DateTime, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    order_id   = Column(String(36), primary_key=True)
    cl_ord_id  = Column(String(64), nullable=False)
    account    = Column(String(64), nullable=False)
    symbol     = Column(String(16), nullable=False)
    side       = Column(String(1),  nullable=False)
    ord_type   = Column(String(1),  nullable=False)
    quantity   = Column(Numeric(20, 8), nullable=False)
    price      = Column(Numeric(20, 8), nullable=True)
    status     = Column(String(1),  nullable=False, default="A")
    session_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    executions = relationship("Execution", back_populates="order")


class Execution(Base):
    __tablename__ = "executions"

    exec_id   = Column(String(36), primary_key=True)
    order_id  = Column(String(36), ForeignKey("orders.order_id"), nullable=False)
    exec_type = Column(String(1),  nullable=False)
    last_qty  = Column(Numeric(20, 8), nullable=False)
    last_px   = Column(Numeric(20, 8), nullable=False)
    cum_qty   = Column(Numeric(20, 8), nullable=False)
    avg_px    = Column(Numeric(20, 8), nullable=False)
    leaves_qty = Column(Numeric(20, 8), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="executions")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("account", "symbol"),)

    id        = Column(String(36), primary_key=True)
    account   = Column(String(64), nullable=False)
    symbol    = Column(String(16), nullable=False)
    net_qty   = Column(Numeric(20, 8), nullable=False, default=0)
    avg_cost  = Column(Numeric(20, 8), nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
