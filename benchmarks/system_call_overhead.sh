#!/bin/bash

echo "🔧 System Call Overhead Benchmark (1,000 requests - OS Tax Analysis)"
echo "================================================================="

# Helper: get first PID listening on a port
get_pid_by_port() {
    lsof -ti:$1 | head -n 1
}

########################################
# TEST 1: REST
########################################
echo ""
echo "📊 Testing REST System Call Overhead..."
echo "Make sure REST server is running on port 8080"

REST_PID=$(get_pid_by_port 8080)
if [ -z "$REST_PID" ]; then
    echo "❌ REST server not found on port 8080. Start it with:"
    echo "   uvicorn rest_server:app --host 0.0.0.0 --port 8080 --workers 1"
    exit 1
fi

echo "✅ Found REST server with PID: $REST_PID"

echo "🔥 Warming up REST server (1 request to force lazy library loads)..."
curl -s -X POST http://localhost:8080/api/transaction \
    -H "Content-Type: application/json" \
    -d '{"transaction_id":"warmup","amount":0.0}' > /dev/null

# Clean old strace file
rm -f /tmp/rest_strace.txt

echo "🔍 Attaching strace to REST server PID $REST_PID (following threads with -f)..."
strace -f -c -p "$REST_PID" -o /tmp/rest_strace.txt 2>/dev/null &
STRACE_REST_PID=$!
sleep 2   # give strace time to attach before firing requests

echo "📤 Sending 1,000 REST requests over persistent session..."

./.venv/bin/python3 - <<EOF
import requests
import sys
import time
sys.path.append('.')
from payload_generator import generate_10kb_payload

session = requests.Session()
payload = generate_10kb_payload()
headers = {"Content-Type": "application/json"}

for i in range(1, 1001):
    try:
        session.post('http://localhost:8080/api/transaction', json=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"REST Error at {i}: {e}", file=sys.stderr)

    if i % 100 == 0:
        print(f"   Sent {i} requests...", file=sys.stderr)
        time.sleep(0.05)
EOF

sleep 1   # ensure all in-flight responses have been logged by strace
# SIGINT causes strace -c to flush and write its summary table
pkill -INT -x strace
sleep 2   # give strace time to write the output file
wait $STRACE_REST_PID 2>/dev/null

echo "✅ REST system call capture complete"

########################################
# COOL DOWN
########################################
echo "⏱️  Cooling down 5 seconds..."
sleep 5

########################################
# TEST 2: gRPC
########################################
echo ""
echo "📊 Testing gRPC System Call Overhead..."
echo "Make sure gRPC server is running on port 50051"

GRPC_PID=$(get_pid_by_port 50051)
if [ -z "$GRPC_PID" ]; then
    echo "❌ gRPC server not found on port 50051. Start it with:"
    echo "   python3 grpc_server.py"
    exit 1
fi

echo "✅ Found gRPC server with PID: $GRPC_PID"

echo "🔥 Warming up gRPC server (1 request to force lazy library loads)..."
./.venv/bin/python3 - <<EOF > /dev/null
import grpc
import sys
sys.path.append('.')
import transaction_pb2
import transaction_pb2_grpc
channel = grpc.insecure_channel('localhost:50051')
stub = transaction_pb2_grpc.TransactionServiceStub(channel)
try:
    stub.ProcessTransaction(transaction_pb2.Transaction(transaction_id="warmup", amount=0.0), timeout=2)
except:
    pass
EOF

# Clean old strace file
rm -f /tmp/grpc_strace.txt

echo "🔍 Attaching strace to gRPC server PID $GRPC_PID (following threads with -f)..."
strace -f -c -p "$GRPC_PID" -o /tmp/grpc_strace.txt 2>/dev/null &
STRACE_GRPC_PID=$!
sleep 2   # give strace time to attach

echo "📤 Sending 1,000 gRPC requests over persistent channel..."

./.venv/bin/python3 - <<EOF
import grpc
import sys
import time
sys.path.append('.')
import transaction_pb2
import transaction_pb2_grpc
from payload_generator import generate_10kb_payload

channel = grpc.insecure_channel('localhost:50051')
stub = transaction_pb2_grpc.TransactionServiceStub(channel)
payload = generate_10kb_payload()

request = transaction_pb2.Transaction(
    transaction_id=payload['transaction_id'],
    timestamp=payload['timestamp'],
    user_id=payload['user_id'],
    event_type=payload['event_type'],
    amount=payload['amount'],
    padding=payload['padding']
)

for i in range(1, 1001):
    try:
        stub.ProcessTransaction(request, timeout=5)
    except Exception as e:
        print(f"gRPC Error at {i}: {e}", file=sys.stderr)

    if i % 100 == 0:
        print(f"   Sent {i} requests...", file=sys.stderr)
        time.sleep(0.05)
EOF

sleep 1   # ensure all in-flight responses have been logged by strace
# SIGINT causes strace -c to flush and write its summary table
pkill -INT -x strace
sleep 2   # give strace time to write the output file
wait $STRACE_GRPC_PID 2>/dev/null

echo "✅ gRPC system call capture complete"

########################################
# RESULTS
########################################
echo ""
echo "========================================================"
echo "📊 PILLAR 4 RESULTS: System Call Overhead"
echo "========================================================"

echo ""
echo "🔵 REST Server Syscall Summary (1,000 requests):"
if [ -s "/tmp/rest_strace.txt" ]; then
    cat /tmp/rest_strace.txt
else
    echo "   ❌ File empty or missing: /tmp/rest_strace.txt"
fi

echo ""
echo "🟢 gRPC Server Syscall Summary (1,000 requests):"
if [ -s "/tmp/grpc_strace.txt" ]; then
    cat /tmp/grpc_strace.txt
else
    echo "   ❌ File empty or missing: /tmp/grpc_strace.txt"
fi

echo ""
echo "✅ Pillar 4 benchmark complete!"
echo "🎯 Key: compare epoll_wait, read, write call counts between REST and gRPC."
echo "   Lower total calls = lower OS kernel tax = better protocol efficiency."
