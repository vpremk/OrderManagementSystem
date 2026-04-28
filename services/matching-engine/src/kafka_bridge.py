from __future__ import annotations
from decimal import Decimal
from confluent_kafka import Producer
from oms_shared.models import (
    OrderValidatedEvent, FillEvent, MarketDataUpdate, ExecType, Side,
)
from oms_shared.kafka_utils import publish, TOPIC_EXECUTIONS_FILLS, TOPIC_MARKET_DATA_UPDATES
from oms_shared.telemetry import fills_total
from order_book import Fill
import structlog

log = structlog.get_logger()


def publish_fills(producer: Producer, fills: list[Fill], original: OrderValidatedEvent) -> None:
    cum_qty_taker = Decimal("0")
    cum_qty_maker: dict[str, Decimal] = {}

    for fill in fills:
        cum_qty_taker += fill.quantity
        cum_qty_maker[fill.maker_order_id] = cum_qty_maker.get(fill.maker_order_id, Decimal("0")) + fill.quantity

    for i, fill in enumerate(fills):
        is_last_taker = (i == len(fills) - 1)
        taker_remaining = original.quantity - cum_qty_taker

        # Taker fill
        taker_fill = FillEvent(
            order_id=fill.taker_order_id,
            cl_ord_id=fill.taker_cl_ord_id,
            account=fill.taker_account,
            symbol=fill.symbol,
            side=fill.side,
            exec_type=ExecType.FILL if taker_remaining == 0 else ExecType.PARTIAL_FILL,
            last_qty=fill.quantity,
            last_px=fill.price,
            cum_qty=cum_qty_taker,
            leaves_qty=taker_remaining,
            avg_px=fill.price,
            session_id=fill.taker_session_id,
        )
        publish(producer, TOPIC_EXECUTIONS_FILLS, taker_fill.order_id, taker_fill)

        # Maker fill
        maker_cum = cum_qty_maker[fill.maker_order_id]
        maker_fill = FillEvent(
            order_id=fill.maker_order_id,
            cl_ord_id=fill.maker_cl_ord_id,
            account=fill.maker_account,
            symbol=fill.symbol,
            side=Side.SELL if fill.side == Side.BUY else Side.BUY,
            exec_type=ExecType.FILL,
            last_qty=fill.quantity,
            last_px=fill.price,
            cum_qty=maker_cum,
            leaves_qty=Decimal("0"),
            avg_px=fill.price,
            session_id=fill.maker_session_id,
        )
        publish(producer, TOPIC_EXECUTIONS_FILLS, maker_fill.order_id, maker_fill)

        fills_total.labels(symbol=fill.symbol, side=fill.side.value).inc()
        log.info("matching.fill", symbol=fill.symbol, price=str(fill.price), qty=str(fill.quantity))


def publish_market_data(producer: Producer, symbol: str, snapshot: dict, last_px: Decimal | None = None) -> None:
    update = MarketDataUpdate(
        symbol=symbol,
        bids=snapshot["bids"],
        asks=snapshot["asks"],
        last_trade_px=str(last_px) if last_px else None,
    )
    publish(producer, TOPIC_MARKET_DATA_UPDATES, symbol, update)
