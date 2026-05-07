import uvicorn
import structlog
from oms_shared.telemetry import setup_logging, setup_tracing, start_metrics_server
import settlement_repo as repo
import settlement_engine

log = structlog.get_logger()


def main() -> None:
    setup_logging("settlement-service")
    setup_tracing("settlement-service")
    start_metrics_server(8000)

    repo.init_db()
    settlement_engine.start()

    log.info("settlement.service.started")
    uvicorn.run("api:app", host="0.0.0.0", port=8004, log_config=None)


if __name__ == "__main__":
    main()
