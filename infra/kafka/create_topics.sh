#!/bin/bash
set -e

BOOTSTRAP=${KAFKA_BOOTSTRAP:-kafka:9092}

wait_for_kafka() {
    echo "Waiting for Kafka at $BOOTSTRAP..."
    until kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --list > /dev/null 2>&1; do
        sleep 2
    done
    echo "Kafka is ready."
}

create_topic() {
    local topic=$1
    local partitions=${2:-3}
    local replication=${3:-1}
    kafka-topics.sh --bootstrap-server "$BOOTSTRAP" \
        --create --if-not-exists \
        --topic "$topic" \
        --partitions "$partitions" \
        --replication-factor "$replication"
    echo "Topic: $topic"
}

wait_for_kafka

create_topic "orders.new"             3 1
create_topic "orders.validated"       3 1
create_topic "orders.rejected"        1 1
create_topic "orders.cancel"          3 1
create_topic "executions.fills"       3 1
create_topic "executions.reports"     3 1
create_topic "market.data.updates"    3 1

echo "All topics created."
