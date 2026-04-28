from __future__ import annotations
import structlog
from oms_shared.models import OrderValidatedEvent
from oms_shared.kafka_utils import (
    make_producer, make_consumer, consume_loop,
    TOPIC_ORDERS_VALIDATED, TOPIC_ORDERS_CANCEL,
)
from oms_shared.telemetry import setup_logging, setup_tracing, start_metrics_server
from order_book import OrderBook
from kafka_bridge import publish_fills, publish_market_data

log = structlog.get_logger()

_books: dict[str, OrderBook] = {}
_producer = None


def get_book(symbol: str) -> OrderBook:
    if symbol not in _books:
        _books[symbol] = OrderBook(symbol)
    return _books[symbol]


def handle_message(topic: str, payload: dict) -> None:
    if topic == TOPIC_ORDERS_VALIDATED:
        _handle_order(payload)
    elif topic == TOPIC_ORDERS_CANCEL:
        _handle_cancel(payload)


def _handle_order(payload: dict) -> None:
    order = OrderValidatedEvent(**payload)
    book = get_book(order.symbol)
    fills = book.add_order(order)
    last_px = fills[-1].price if fills else None
    if fills:
        publish_fills(_producer, fills, order)
    publish_market_data(_producer, order.symbol, book.snapshot(), last_px)
    log.info("matching.order.processed", order_id=order.order_id, fills=len(fills))


def _handle_cancel(payload: dict) -> None:
    order_id = payload.get("order_id", "")
    for symbol, book in _books.items():
        if book.cancel_order(order_id):
            publish_market_data(_producer, symbol, book.snapshot())
            log.info("matching.order.canceled", order_id=order_id, symbol=symbol)
            return
    log.warning("matching.cancel.not_found", order_id=order_id)


def main() -> None:
    global _producer
    setup_logging("matching-engine")
    setup_tracing("matching-engine")
    start_metrics_server(8000)

    _producer = make_producer()
    consumer = make_consumer(
        "matching-engine",
        [TOPIC_ORDERS_VALIDATED, TOPIC_ORDERS_CANCEL],
    )

    log.info("matching.engine.started")
    consume_loop(consumer, handle_message)


if __name__ == "__main__":
    main()
