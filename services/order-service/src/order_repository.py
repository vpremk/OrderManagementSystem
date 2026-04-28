from __future__ import annotations
import os
import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Order, Execution, Position
from oms_shared.models import (
    OrderValidatedEvent, OrderRejectedEvent, FillEvent,
    OrdStatus, ExecType,
)
import structlog

log = structlog.get_logger()

DB_URL = os.getenv("DATABASE_URL", "postgresql://oms:oms@postgres:5432/oms")

engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    log.info("db.initialized")


# ── Write helpers ────────────────────────────────────────────────────────────

def upsert_order_new(event: OrderValidatedEvent) -> None:
    with SessionLocal() as session:
        order = Order(
            order_id=event.order_id,
            cl_ord_id=event.cl_ord_id,
            account=event.account,
            symbol=event.symbol,
            side=event.side.value,
            ord_type=event.ord_type.value,
            quantity=event.quantity,
            price=event.price,
            status=OrdStatus.NEW.value,
            session_id=event.session_id,
        )
        session.merge(order)
        session.commit()


def record_rejection(event: OrderRejectedEvent) -> None:
    with SessionLocal() as session:
        order = Order(
            order_id=event.order_id,
            cl_ord_id=event.cl_ord_id,
            account=event.account,
            symbol=event.symbol,
            side="?",
            ord_type="?",
            quantity=0,
            status=OrdStatus.REJECTED.value,
            session_id=event.session_id,
        )
        session.merge(order)
        session.commit()


def record_fill(event: FillEvent) -> tuple[OrdStatus, Decimal, Decimal]:
    with SessionLocal() as session:
        exec_row = Execution(
            exec_id=event.exec_id,
            order_id=event.order_id,
            exec_type=event.exec_type.value,
            last_qty=event.last_qty,
            last_px=event.last_px,
            cum_qty=event.cum_qty,
            avg_px=event.avg_px,
            leaves_qty=event.leaves_qty,
        )
        session.add(exec_row)

        order = session.get(Order, event.order_id)
        if order:
            if event.leaves_qty == 0:
                order.status = OrdStatus.FILLED.value
            else:
                order.status = OrdStatus.PARTIALLY_FILLED.value

        _update_position(session, event)
        session.commit()

        ord_status = OrdStatus(order.status) if order else OrdStatus.FILLED
        return ord_status, event.cum_qty, event.avg_px


def cancel_order_db(order_id: str) -> None:
    with SessionLocal() as session:
        session.execute(
            text("UPDATE orders SET status=:s, updated_at=NOW() WHERE order_id=:id"),
            {"s": OrdStatus.CANCELED.value, "id": order_id},
        )
        session.commit()


def _update_position(session: Session, event: FillEvent) -> None:
    sign = Decimal("1") if event.side.value == "1" else Decimal("-1")
    delta = sign * event.last_qty

    pos = session.execute(
        text("SELECT net_qty, avg_cost FROM positions WHERE account=:a AND symbol=:s FOR UPDATE"),
        {"a": event.account, "s": event.symbol},
    ).fetchone()

    if pos is None:
        session.execute(
            text(
                "INSERT INTO positions (id, account, symbol, net_qty, avg_cost) "
                "VALUES (:id, :a, :s, :qty, :cost) "
                "ON CONFLICT (account, symbol) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "a": event.account, "s": event.symbol,
             "qty": delta, "cost": event.last_px},
        )
    else:
        new_qty = Decimal(str(pos.net_qty)) + delta
        if new_qty == 0:
            new_cost = Decimal("0")
        elif sign > 0:
            old_cost = Decimal(str(pos.avg_cost)) * Decimal(str(pos.net_qty))
            new_cost = (old_cost + event.last_px * event.last_qty) / new_qty
        else:
            new_cost = Decimal(str(pos.avg_cost))

        session.execute(
            text("UPDATE positions SET net_qty=:qty, avg_cost=:cost WHERE account=:a AND symbol=:s"),
            {"qty": new_qty, "cost": new_cost, "a": event.account, "s": event.symbol},
        )


# ── Read helpers ─────────────────────────────────────────────────────────────

def get_order(order_id: str) -> Optional[dict]:
    with SessionLocal() as session:
        o = session.get(Order, order_id)
        if o is None:
            return None
        return {c.name: getattr(o, c.name) for c in Order.__table__.columns}


def get_orders(
    account: Optional[str] = None,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    with SessionLocal() as session:
        q = session.query(Order)
        if account:
            q = q.filter(Order.account == account)
        if symbol:
            q = q.filter(Order.symbol == symbol)
        if status:
            q = q.filter(Order.status == status)
        return [
            {c.name: str(getattr(o, c.name)) if getattr(o, c.name) is not None else None
             for c in Order.__table__.columns}
            for o in q.order_by(Order.created_at.desc()).limit(500).all()
        ]


def get_executions(order_id: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.query(Execution).filter(Execution.order_id == order_id)\
            .order_by(Execution.created_at.asc()).all()
        return [
            {c.name: str(getattr(e, c.name)) if getattr(e, c.name) is not None else None
             for c in Execution.__table__.columns}
            for e in rows
        ]


def get_all_executions(
    symbol: Optional[str] = None,
    account: Optional[str] = None,
) -> list[dict]:
    with SessionLocal() as session:
        q = session.query(Execution).join(Order, Execution.order_id == Order.order_id)
        if symbol:
            q = q.filter(Order.symbol == symbol)
        if account:
            q = q.filter(Order.account == account)
        rows = q.order_by(Execution.created_at.desc()).limit(500).all()
        return [
            {c.name: str(getattr(e, c.name)) if getattr(e, c.name) is not None else None
             for c in Execution.__table__.columns}
            for e in rows
        ]


def get_positions(account: Optional[str] = None) -> list[dict]:
    with SessionLocal() as session:
        q = session.query(Position)
        if account:
            q = q.filter(Position.account == account)
        return [
            {c.name: str(getattr(p, c.name)) if getattr(p, c.name) is not None else None
             for c in Position.__table__.columns}
            for p in q.all()
        ]
