from __future__ import annotations
import os
import signal
import threading
import quickfix as fix
import structlog
from oms_shared.models import MarketDataUpdate
from oms_shared.kafka_utils import make_consumer, consume_loop, TOPIC_MARKET_DATA_UPDATES
from oms_shared.telemetry import setup_logging, setup_tracing, start_metrics_server
from fix_application import MarketDataApplication
from publisher import publish_snapshot

log = structlog.get_logger()

CONFIG_PATH = os.getenv("FIX_MD_CONFIG", "/app/config/fix44_md.cfg")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))

_app: MarketDataApplication | None = None


def handle_market_data(topic: str, payload: dict) -> None:
    update = MarketDataUpdate(**payload)
    if _app:
        publish_snapshot(_app, update)


def main() -> None:
    global _app
    setup_logging("market-data-service")
    setup_tracing("market-data-service")
    start_metrics_server(METRICS_PORT)

    settings = fix.SessionSettings(CONFIG_PATH)
    _app = MarketDataApplication()
    store_factory = fix.FileStoreFactory(settings)
    log_factory = fix.FileLogFactory(settings)
    acceptor = fix.SocketAcceptor(_app, store_factory, settings, log_factory)
    acceptor.start()

    stop_event = threading.Event()
    consumer = make_consumer("market-data-service", [TOPIC_MARKET_DATA_UPDATES])

    consumer_thread = threading.Thread(
        target=consume_loop,
        args=(consumer, handle_market_data, stop_event),
        daemon=True,
    )
    consumer_thread.start()
    log.info("market_data.service.started")

    def _sig(s, f):
        stop_event.set()

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    stop_event.wait()
    acceptor.stop()


if __name__ == "__main__":
    main()
