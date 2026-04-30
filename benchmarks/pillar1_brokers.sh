#!/bin/bash
# Pillar 1: Async Broker Benchmark (JVM Native Tools)
# Bypasses Python/GIL entirely. Uses official JVM CLI tools.
# Output saved to benchmarks/kafka_out.txt and benchmarks/rabbitmq_out.txt
# for parsing by benchmarks/parse_results.py.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KAFKA_OUT="$SCRIPT_DIR/kafka_out.txt"
RABBITMQ_OUT="$SCRIPT_DIR/rabbitmq_out.txt"

echo "========================================================="
echo "  PILLAR 1: ASYNC BROKER BENCHMARK (JVM NATIVE TOOLS)"
echo "========================================================="
echo ""
echo "Note: Bypasses Python entirely to avoid GIL-induced latency"
echo "artifacts and GC interference. Uses official compiled Java"
echo "utilities provided by the broker maintainers."
echo ""

########################################
# KAFKA
########################################
echo "▶ KAFKA BENCHMARK"
echo "---------------------------------------------------------"
echo "kafka-producer-perf-test: 100,000 records, 10KB payload, acks=all"
echo "Output: $KAFKA_OUT"
echo ""

# Run inside the Kafka container where the JVM tools are installed.
# acks=all ensures full ISR acknowledgement — measures durable write latency.
# --throughput -1 = unlimited (saturate the broker).
docker exec brokers-kafka-1 \
    kafka-producer-perf-test \
    --topic test_topic \
    --num-records 100000 \
    --record-size 10240 \
    --throughput -1 \
    --producer-props bootstrap.servers=localhost:9092 acks=all \
    2>&1 | tee "$KAFKA_OUT"

echo ""
echo "Kafka results saved to $KAFKA_OUT"

########################################
# RABBITMQ
########################################
echo ""
echo "▶ RABBITMQ BENCHMARK"
echo "---------------------------------------------------------"
echo "rabbitmq-perf-test: 1 producer, 1 consumer, 10KB payload, 60s"
echo "Output: $RABBITMQ_OUT"
echo ""

# Run using the official pivotalrabbitmq/perf-test Docker image.
# Connects to RabbitMQ on the brokers_default network.
# -x 1  : 1 producer
# -y 1  : 1 consumer (end-to-end measurement)
# -s 10240 : 10KB message body
# --time 60: run for 60 seconds
# -a    : auto-ack
docker run --rm \
    --network brokers_default \
    pivotalrabbitmq/perf-test:latest \
    --uri "amqp://guest:guest@brokers-rabbitmq-1:5672" \
    -x 1 -y 1 \
    -s 10240 \
    --time 60 \
    -a \
    2>&1 | tee "$RABBITMQ_OUT"

echo ""
echo "RabbitMQ results saved to $RABBITMQ_OUT"
echo ""
echo "========================================================="
echo "Pillar 1 broker benchmarks complete."
echo "Run: python3 benchmarks/parse_results.py"
echo "========================================================="
