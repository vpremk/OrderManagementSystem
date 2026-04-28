import uvicorn
import structlog
from oms_shared.kafka_utils import make_producer
from oms_shared.telemetry import setup_logging, setup_tracing
import order_repository as repo
import kafka_consumer

log = structlog.get_logger()


def main() -> None:
    setup_logging("order-service")
    setup_tracing("order-service")

    repo.init_db()
    producer = make_producer()
    kafka_consumer.start(producer)

    import api
    api.set_producer(producer)

    log.info("order_service.started")
    uvicorn.run("api:app", host="0.0.0.0", port=8001, log_config=None)


if __name__ == "__main__":
    main()
