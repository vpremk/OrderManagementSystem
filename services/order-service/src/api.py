from __future__ import annotations
from decimal import Decimal
from typing import Optional
import uuid
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from pydantic import BaseModel
from confluent_kafka import Producer
from oms_shared.models import OrderEvent, Side, OrdType
from oms_shared.kafka_utils import make_producer, publish, TOPIC_ORDERS_NEW, TOPIC_ORDERS_CANCEL
import order_repository as repo

app = FastAPI(title="OMS Order Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

_producer: Producer | None = None


def set_producer(p: Producer) -> None:
    global _producer
    _producer = p


# ── Request models ──────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    cl_ord_id: Optional[str] = None
    account: str
    symbol: str
    side: Side
    ord_type: OrdType
    quantity: Decimal
    price: Optional[Decimal] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/orders")
def list_orders(
    account: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    return repo.get_orders(account=account, symbol=symbol, status=status)


@app.post("/orders", status_code=201)
def create_order(body: CreateOrderRequest):
    if body.ord_type == OrdType.LIMIT and body.price is None:
        raise HTTPException(status_code=422, detail="price is required for limit orders")

    event = OrderEvent(
        cl_ord_id=body.cl_ord_id or f"UI-{uuid.uuid4().hex[:8].upper()}",
        account=body.account,
        symbol=body.symbol,
        side=body.side,
        ord_type=body.ord_type,
        quantity=body.quantity,
        price=body.price,
        session_id="UI:DIRECT",
    )
    publish(_producer, TOPIC_ORDERS_NEW, event.order_id, event)
    return {"order_id": event.order_id, "cl_ord_id": event.cl_ord_id}


@app.delete("/orders/{order_id}", status_code=200)
def cancel_order(order_id: str):
    order = repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] not in ("0", "1", "A"):  # NEW, PARTIALLY_FILLED, PENDING_NEW
        raise HTTPException(status_code=409, detail=f"Order cannot be canceled (status={order['status']})")

    repo.cancel_order_db(order_id)
    publish(_producer, TOPIC_ORDERS_CANCEL, order_id, {"order_id": order_id})
    return {"order_id": order_id, "status": "canceled"}


@app.get("/orders/{order_id}/executions")
def get_order_executions(order_id: str):
    return repo.get_executions(order_id)


@app.get("/executions")
def list_executions(
    symbol: Optional[str] = Query(None),
    account: Optional[str] = Query(None),
):
    return repo.get_all_executions(symbol=symbol, account=account)


@app.get("/positions")
def list_positions(account: Optional[str] = Query(None)):
    return repo.get_positions(account=account)
