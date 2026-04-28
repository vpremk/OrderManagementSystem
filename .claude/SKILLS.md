# Skills & Design Decisions

A reference for the technical skills demonstrated in this codebase and the reasoning behind key choices.

## Financial Domain

### FIX Protocol (4.4)
- **Session layer** — Logon/Logout/Heartbeat/TestRequest/ResendRequest handled by QuickFIX. The application layer only deals with business messages (35=D, 35=8, etc.).
- **CompID pairs** — Each FIX session is identified by `SenderCompID:TargetCompID`. The gateway stores a live map of `session_key → SessionID` objects to route outbound `ExecutionReport` messages back to the originating client.
- **Maker/taker price rule** — On a match, the fill price is always the resting (maker) order's price, not the aggressing (taker) order's price. This is standard exchange behaviour.
- **ExecType vs OrdStatus** — These are distinct FIX fields. `ExecType` describes *what just happened* (0=New, 1=PartialFill, 2=Fill); `OrdStatus` describes *the current state of the order* (0=New, 1=PartiallyFilled, 2=Filled). Both are required in every ExecutionReport.

### Order Book
- **Price-time priority** — Orders at the same price are filled in the order they arrived (FIFO). Implemented with `SortedDict` (O(log n) insertion) + `deque` per price level (O(1) FIFO pop).
- **Bid-side key inversion** — `SortedDict(lambda k: -k)` on the bid side gives descending iteration (highest bid first) without a separate reverse-sorted structure.
- **Market orders** — `price=None` signals a market order. The matching loop skips the price-check and sweeps through all available levels until filled or the opposite side is exhausted.

### Risk Engine
- **Price collar** — Limits are ±`PRICE_COLLAR_PCT` of the *last traded price*, not the mid or reference. This is intentional: collars anchor to where the market last transacted, not a potentially stale reference.
- **Position sign convention** — Long positions are positive, short positions are negative. The risk check uses `abs(projected_position) > limit` so the same limit applies to both sides.
- **Redis for position state** — Position state is kept in Redis (not in-process) so the risk engine can be horizontally scaled without diverging position views.

## Distributed Systems

### Kafka as the backbone
- **Event sourcing** — Every order state change is a Kafka event. The order book in the matching engine and the position cache in the risk engine are derived views, not the source of truth. PostgreSQL (via order-service) is the persistent record.
- **Consumer group isolation** — Each service uses a distinct `group.id`. This means `orders.validated` is consumed independently by both `matching-engine` and `order-service` without coordination.
- **`acks=all`** on the producer — Ensures the broker confirms replication before the producer call returns, preventing silent message loss under broker failure.
- **`auto.offset.reset=earliest`** — Services replay from the beginning of a topic partition on first start. This makes cold-start safe: a newly deployed matching-engine will process all unprocessed orders before accepting new ones.

### Service startup ordering
- `kafka-init` is a short-lived container that creates all topics and exits with code 0. The core services declare `depends_on: kafka-init: condition: service_completed_successfully`, so topic existence is guaranteed before any producer/consumer starts.

## Python Patterns

### Shared package (`oms_shared`)
- Installed as an editable package (`pip install -e /shared/`) into every service image. This avoids copy-pasting Pydantic models and ensures all services share a single canonical definition of `OrderEvent`, `FillEvent`, etc.
- **Pydantic v2** — `model_dump_json()` produces the Kafka payload. `Decimal` fields are serialised as strings to avoid floating-point precision loss across service boundaries.

### Thread model in fix-gateway
- QuickFIX runs its own internal thread pool for session I/O.
- A separate daemon thread polls `executions.reports` from Kafka and calls `fix.Session.sendToTarget()`. QuickFIX's `sendToTarget` is thread-safe, so no locking is needed.
- `threading.Event` is used for clean shutdown: the Kafka consumer loop checks it on every poll timeout.

### `consume_loop` utility
- A single reusable function in `kafka_utils.py` wraps the poll loop, error handling, and JSON deserialisation. All five services call it identically, keeping per-service code focused on business logic.

## Observability

### Structured logging (structlog)
- All log lines are JSON objects emitted to stdout. Promtail scrapes container stdout via the Docker socket and pushes to Loki. Grafana's LogQL can then filter by `service`, `level`, `symbol`, or any other structured field.

### Metrics (Prometheus)
- Three counter types cover the full funnel: `orders_received` → `orders_rejected` (risk drop-off) → `fills` (successful execution).
- `order_latency_seconds` is a Histogram with exchange-relevant buckets (1ms–1s). The p99 panel in Grafana immediately shows tail latency spikes.
- The order-service mounts Prometheus metrics at `/metrics` via `make_asgi_app()` — no separate port needed.

### Tracing (OpenTelemetry → Jaeger)
- Each service initialises a `TracerProvider` with a `BatchSpanProcessor` pointing at Jaeger's OTLP gRPC endpoint (port 4317). Spans are named after the service and the operation (e.g., `risk-engine`, `matching-engine`).
- Trace context propagation across Kafka messages is not wired in this initial version — each service creates root spans. Propagating `traceparent` headers through Kafka message headers is the natural next step.

## Docker

### Build context
- All Dockerfiles use `.` (repo root) as the build context so they can `COPY shared/` before copying service-specific code. This means one `docker build` command can build any service from the repo root, which is what `docker compose` does.

### Layer caching
- `pip install` runs on `requirements.txt` before `COPY src/` so that dependency layers are cached across code-only changes — the most common development cycle.

### Healthchecks
- Every infrastructure container (Kafka, Postgres, Redis, Zookeeper) has a healthcheck. Application services use `depends_on: condition: service_healthy` rather than `sleep` scripts, making startup deterministic.

## What's Not Here (Intentional Scope Limits)

| Feature | Notes |
|---|---|
| TLS on FIX sessions | Add `SocketUseSSL=Y` + cert paths in `fix44.cfg` for production |
| FIX sequence number persistence | Currently resets on reconnect (`ResetOnLogon=Y`). For production, remove that flag and use persistent `FileStore`. |
| Order cancel/replace routing | `_handle_cancel` and `_handle_replace` stubs are in fix-gateway; matching-engine `cancel_order` is implemented and ready to wire up |
| Kafka replication factor > 1 | Set to 1 for single-broker dev. Change `--replication-factor` in `create_topics.sh` and `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR` for multi-broker |
| OTel trace propagation via Kafka | Next step: inject/extract `traceparent` as Kafka message headers |
| Authentication on REST API | Order-service `/orders` and `/positions` are unauthenticated; add an API key middleware for any non-local deployment |
