from __future__ import annotations
import json
import os
from typing import Callable, Any
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
import structlog

log = structlog.get_logger()

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")

TOPIC_ORDERS_NEW = "orders.new"
TOPIC_ORDERS_VALIDATED = "orders.validated"
TOPIC_ORDERS_REJECTED = "orders.rejected"
TOPIC_ORDERS_CANCEL = "orders.cancel"
TOPIC_EXECUTIONS_FILLS = "executions.fills"
TOPIC_EXECUTIONS_REPORTS = "executions.reports"
TOPIC_MARKET_DATA_UPDATES = "market.data.updates"
TOPIC_TRADES = "trades"


def make_producer() -> Producer:
    return Producer({"bootstrap.servers": BOOTSTRAP, "acks": "all"})


def make_consumer(group_id: str, topics: list[str]) -> Consumer:
    c = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    c.subscribe(topics)
    return c


def publish(producer: Producer, topic: str, key: str, payload: Any) -> None:
    data = payload.model_dump_json() if hasattr(payload, "model_dump_json") else json.dumps(payload)
    producer.produce(topic, key=key.encode(), value=data.encode(), callback=_delivery_cb)
    producer.poll(0)


def _delivery_cb(err, msg) -> None:
    if err:
        log.error("kafka.delivery.error", error=str(err))


def consume_loop(consumer: Consumer, handler: Callable[[str, dict], None], stop_event=None) -> None:
    import threading

    _stop = stop_event or threading.Event()
    try:
        while not _stop.is_set():
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())
            try:
                payload = json.loads(msg.value().decode())
                handler(msg.topic(), payload)
            except Exception:
                log.exception("kafka.handler.error", topic=msg.topic())
    finally:
        consumer.close()
