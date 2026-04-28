from __future__ import annotations
import threading
from confluent_kafka import Producer
from oms_shared.models import (
    OrderValidatedEvent, OrderRejectedEvent, FillEvent, ExecutionReportEvent, OrdStatus,
)
from oms_shared.kafka_utils import (
    make_producer, make_consumer, publish, consume_loop,
    TOPIC_ORDERS_VALIDATED, TOPIC_ORDERS_REJECTED,
    TOPIC_EXECUTIONS_FILLS, TOPIC_EXECUTIONS_REPORTS,
)
import order_repository as repo
import structlog

log = structlog.get_logger()

_producer: Producer | None = None
_stop = threading.Event()


def start(producer: Producer) -> None:
    global _producer
    _producer = producer

    t1 = threading.Thread(target=_run_order_consumer, daemon=True)
    t2 = threading.Thread(target=_run_fill_consumer, daemon=True)
    t1.start()
    t2.start()


def _run_order_consumer() -> None:
    consumer = make_consumer("order-service-orders", [TOPIC_ORDERS_VALIDATED, TOPIC_ORDERS_REJECTED])
    consume_loop(consumer, _handle_order, _stop)


def _run_fill_consumer() -> None:
    consumer = make_consumer("order-service-fills", [TOPIC_EXECUTIONS_FILLS])
    consume_loop(consumer, _handle_fill, _stop)


def _handle_order(topic: str, payload: dict) -> None:
    if topic == TOPIC_ORDERS_VALIDATED:
        event = OrderValidatedEvent(**payload)
        repo.upsert_order_new(event)
        log.info("order_service.order.stored", order_id=event.order_id)

        # Send NEW execution report back through FIX gateway
        exec_report = ExecutionReportEvent(
            order_id=event.order_id,
            cl_ord_id=event.cl_ord_id,
            account=event.account,
            symbol=event.symbol,
            side=event.side,
            exec_type="0",  # ExecType.NEW
            last_qty=event.quantity * 0,  # Decimal("0") — no fill yet
            last_px=event.price or event.quantity * 0,
            cum_qty=event.quantity * 0,
            leaves_qty=event.quantity,
            avg_px=event.quantity * 0,
            session_id=event.session_id,
            ord_status=OrdStatus.NEW,
        )
        publish(_producer, TOPIC_EXECUTIONS_REPORTS, event.order_id, exec_report)

    elif topic == TOPIC_ORDERS_REJECTED:
        event = OrderRejectedEvent(**payload)
        repo.record_rejection(event)
        log.info("order_service.order.rejected", order_id=event.order_id)


def _handle_fill(topic: str, payload: dict) -> None:
    fill = FillEvent(**payload)
    ord_status, cum_qty, avg_px = repo.record_fill(fill)

    exec_report = ExecutionReportEvent(
        **fill.model_dump(),
        ord_status=ord_status,
    )
    publish(_producer, TOPIC_EXECUTIONS_REPORTS, fill.order_id, exec_report)
    log.info("order_service.fill.processed", order_id=fill.order_id, exec_type=fill.exec_type)
