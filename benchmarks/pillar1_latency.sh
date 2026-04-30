#!/bin/bash
# Pillar 1: Throughput & Tail Latency
# REST: wrk (HTTP/1.1 + JSON) against servers/rest_server.py on port 8000
# gRPC: ghz (HTTP/2 + Protobuf) against servers/grpc_server.py on port 50051
# Config: 10 concurrent connections, 60s duration, 10KB payload
# Results saved to benchmarks/rest_10.txt and benchmarks/grpc_10.txt

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
REST_URL="http://127.0.0.1:8000"
GRPC_HOST="127.0.0.1:50051"
CONCURRENCY=10
DURATION=60s
REST_OUT="$SCRIPT_DIR/rest_10.txt"
GRPC_OUT="$SCRIPT_DIR/grpc_10.txt"

echo "Pillar 1: Throughput & Tail Latency"
echo "====================================="
echo "Concurrency: $CONCURRENCY  |  Duration: $DURATION  |  Payload: 10KB"
echo ""

########################################
# Verify servers are up
########################################
echo "Checking REST server at $REST_URL ..."
if ! curl -sf --connect-timeout 3 "$REST_URL/transaction" -X POST \
    -H "Content-Type: application/json" \
    -d '{"transaction_id":"ping","timestamp":1.0,"user_id":1,"amount":1.0,"currency":"USD","description":"ping","merchant_code":"P","metadata":"x"}' \
    > /dev/null; then
    echo "ERROR: REST server not responding. Start it with:"
    echo "  uvicorn servers.rest_server:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"
    exit 1
fi
echo "REST server OK"

echo "Checking gRPC server at $GRPC_HOST ..."
if ! nc -z 127.0.0.1 50051 2>/dev/null; then
    echo "ERROR: gRPC server not responding. Start it with:"
    echo "  python3 servers/grpc_server.py"
    exit 1
fi
echo "gRPC server OK"
echo ""

########################################
# REST benchmark — wrk
########################################
echo "--- REST benchmark (wrk) ---"
echo "Command: wrk -t2 -c$CONCURRENCY -d$DURATION --latency -s benchmarks/scripts/post.lua $REST_URL/transaction"
echo ""

wrk -t2 -c"$CONCURRENCY" -d"$DURATION" --latency \
    -s "$SCRIPT_DIR/scripts/post.lua" \
    "$REST_URL/transaction" | tee "$REST_OUT"

echo ""
echo "REST results saved to $REST_OUT"
echo "Cooling down 10s..."
sleep 10

########################################
# gRPC benchmark — ghz
########################################
echo ""
echo "--- gRPC benchmark (ghz) ---"

METADATA=$(python3 -c "print('X'*10000)")

echo "Command: ghz --insecure --proto payload_gen/schema.proto --call payload_gen.BenchmarkService/ProcessTransaction -c $CONCURRENCY -z $DURATION ..."
echo ""

ghz --insecure \
    --proto "$ROOT_DIR/payload_gen/schema.proto" \
    --call payload_gen.BenchmarkService/ProcessTransaction \
    -c "$CONCURRENCY" \
    -z "$DURATION" \
    -d "{\"transaction_id\":\"bench\",\"timestamp\":1.0,\"user_id\":1000,\"amount\":99.99,\"currency\":\"USD\",\"description\":\"benchmark\",\"merchant_code\":\"M01\",\"metadata\":\"$METADATA\"}" \
    "$GRPC_HOST" | tee "$GRPC_OUT"

echo ""
echo "gRPC results saved to $GRPC_OUT"
echo ""
echo "====================================="
echo "Pillar 1 complete. Results in:"
echo "  $REST_OUT"
echo "  $GRPC_OUT"
