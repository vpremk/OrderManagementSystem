import structlog
from confluent_kafka import Producer
from oms_shared.models import OrderEvent, OrderValidatedEvent, OrderRejectedEvent
from oms_shared.kafka_utils import (
    make_producer, make_consumer, publish, consume_loop,
    TOPIC_ORDERS_NEW, TOPIC_ORDERS_VALIDATED, TOPIC_ORDERS_REJECTED,
)
from oms_shared.telemetry import setup_logging, setup_tracing, start_metrics_server, orders_rejected as rejected_counter
import risk_checks

log = structlog.get_logger()

_producer: Producer | None = None


def handle_order(topic: str, payload: dict) -> None:
    order = OrderEvent(**payload)
    passed, reason = risk_checks.check(order)

    if passed:
        validated = OrderValidatedEvent(**order.model_dump())
        publish(_producer, TOPIC_ORDERS_VALIDATED, order.order_id, validated)
        log.info("risk.order.validated", order_id=order.order_id, symbol=order.symbol)
    else:
        rejected = OrderRejectedEvent(
            order_id=order.order_id,
            cl_ord_id=order.cl_ord_id,
            account=order.account,
            symbol=order.symbol,
            session_id=order.session_id,
            reject_reason=reason,
        )
        publish(_producer, TOPIC_ORDERS_REJECTED, order.order_id, rejected)
        rejected_counter.labels(service="risk-engine", reason=reason[:50]).inc()
        log.info("risk.order.rejected", order_id=order.order_id, reason=reason)


def main() -> None:
    global _producer
    setup_logging("risk-engine")
    setup_tracing("risk-engine")
    start_metrics_server(8000)

    risk_checks.load_instruments()
    _producer = make_producer()
    consumer = make_consumer("risk-engine", [TOPIC_ORDERS_NEW])

    log.info("risk.engine.started")
    consume_loop(consumer, handle_order)


if __name__ == "__main__":
    main()
