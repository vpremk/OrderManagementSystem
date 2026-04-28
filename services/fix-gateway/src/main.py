import os
import signal
import quickfix as fix
import structlog
from oms_shared.telemetry import setup_logging, setup_tracing, start_metrics_server
from fix_application import OMSApplication

log = structlog.get_logger()

CONFIG_PATH = os.getenv("FIX_CONFIG", "/app/config/fix44.cfg")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))


def main() -> None:
    setup_logging("fix-gateway")
    setup_tracing("fix-gateway")
    start_metrics_server(METRICS_PORT)

    settings = fix.SessionSettings(CONFIG_PATH)
    application = OMSApplication()
    store_factory = fix.FileStoreFactory(settings)
    log_factory = fix.FileLogFactory(settings)
    acceptor = fix.SocketAcceptor(application, store_factory, settings, log_factory)

    application.start_consumer()
    acceptor.start()
    log.info("fix.gateway.started", config=CONFIG_PATH)

    stop = False
    def _sig(s, f):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    import time
    while not stop:
        time.sleep(1)

    log.info("fix.gateway.stopping")
    application.stop()
    acceptor.stop()


if __name__ == "__main__":
    main()
