#!/bin/bash
# Pillar 4: Kernel System Call Overhead
# Attaches strace -c to the server worker process while 1000 requests are sent.
# strace -c counts syscalls accurately; wall-clock times from strace are discarded
# (ptrace overhead inflates them by 2-10x — this is documented in methodology caveats).
# Requires: strace, all 3 servers running (TCP on 9000, REST on 8000, gRPC on 50051).
# Order: TCP (baseline) → REST → gRPC

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
N=1000
TCP_STRACE="/tmp/p4_tcp_strace.txt"
REST_STRACE="/tmp/p4_rest_strace.txt"
GRPC_STRACE="/tmp/p4_grpc_strace.txt"

echo "Pillar 4: Kernel System Call Overhead ($N requests per protocol)"
echo "================================================================="
echo "NOTE: strace syscall COUNTS are accurate. Timing values are discarded"
echo "      due to ptrace instrumentation overhead (2-10x slowdown)."
echo "      Order: TCP (baseline) → REST → gRPC"
echo ""

########################################
# Helper: find the worker PID
# For uvicorn --workers 1, the single worker is a child of the master.
# We grab the child PID (not the master) so strace sees actual I/O syscalls.
########################################
get_worker_pid() {
    local port=$1
    local master_pid
    master_pid=$(lsof -ti:"$port" | head -n 1)
    if [ -z "$master_pid" ]; then
        echo ""
        return
    fi
    # Try to find a child process (uvicorn worker)
    local child_pid
    child_pid=$(pgrep -P "$master_pid" 2>/dev/null | head -n 1)
    if [ -n "$child_pid" ]; then
        echo "$child_pid"
    else
        # Single-process server (grpc, tcp, or uvicorn with 1 worker in same process)
        echo "$master_pid"
    fi
}

########################################
# TCP  (Speed-of-Light Baseline)
########################################
echo "[TCP] Locating server process on port 9000..."
TCP_PID=$(get_worker_pid 9000)
if [ -z "$TCP_PID" ]; then
    echo "ERROR: TCP server not found on port 9000."
    echo "Start with: python3 servers/tcp_server.py"
    exit 1
fi
echo "[TCP] Attaching strace to PID $TCP_PID"

# Warmup — 10 requests before attaching strace so import/startup noise is excluded
"$ROOT_DIR/.venv/bin/python3" - <<'WARMUP_EOF' > /dev/null 2>&1
import socket, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath('.')), 'payload_gen'))
sys.path.insert(0, 'payload_gen')
from generator import PAYLOAD_10KB
payload = json.dumps(PAYLOAD_10KB).encode()
psize = len(payload)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 9000))
sock.settimeout(5)
for _ in range(10):
    sock.sendall(payload)
    r = 0
    while r < psize:
        c = sock.recv(psize - r)
        if not c: break
        r += len(c)
sock.close()
WARMUP_EOF

rm -f "$TCP_STRACE"
strace -f -c -p "$TCP_PID" 2>"$TCP_STRACE" &
STRACE_PID=$!
sleep 2

echo "[TCP] Sending $N requests..."
"$ROOT_DIR/.venv/bin/python3" - <<EOF
import socket, json, sys, os
sys.path.insert(0, '$ROOT_DIR/payload_gen')
from generator import PAYLOAD_10KB
payload = json.dumps(PAYLOAD_10KB).encode()
psize = len(payload)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 9000))
sock.settimeout(5)
for i in range(1, $N + 1):
    try:
        sock.sendall(payload)
        r = 0
        while r < psize:
            c = sock.recv(psize - r)
            if not c: break
            r += len(c)
    except Exception as e:
        print(f"Error {i}: {e}", file=sys.stderr)
    if i % 200 == 0:
        print(f"  {i}/$N sent", file=sys.stderr)
sock.close()
EOF

sleep 1
kill -INT $STRACE_PID 2>/dev/null || true
sleep 3
wait $STRACE_PID 2>/dev/null || true
echo "[TCP] strace capture complete."

sleep 5

########################################
# REST
########################################
echo ""
echo "[REST] Locating server process on port 8000..."
REST_PID=$(get_worker_pid 8000)
if [ -z "$REST_PID" ]; then
    echo "ERROR: REST server not found on port 8000."
    echo "Start with: uvicorn servers.rest_server:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"
    exit 1
fi
echo "[REST] Attaching strace to PID $REST_PID"

# Warmup
curl -sf -X POST http://127.0.0.1:8000/transaction \
    -H "Content-Type: application/json" \
    -d '{"transaction_id":"warmup","timestamp":1.0,"user_id":1,"amount":1.0,"currency":"USD","description":"w","merchant_code":"W","metadata":"x"}' \
    > /dev/null

rm -f "$REST_STRACE"
strace -f -c -p "$REST_PID" 2>"$REST_STRACE" &
STRACE_PID=$!
sleep 2

echo "[REST] Sending $N requests..."
"$ROOT_DIR/.venv/bin/python3" - <<EOF
import sys, requests, time
sys.path.insert(0, '$ROOT_DIR/payload_gen')
from generator import PAYLOAD_10KB
import json

session = requests.Session()
headers = {"Content-Type": "application/json"}
body = json.dumps(PAYLOAD_10KB)

for i in range(1, $N + 1):
    try:
        session.post('http://127.0.0.1:8000/transaction', data=body, headers=headers, timeout=10)
    except Exception as e:
        print(f"Error {i}: {e}", file=sys.stderr)
    if i % 200 == 0:
        print(f"  {i}/$N sent", file=sys.stderr)
EOF

sleep 1
kill -INT $STRACE_PID 2>/dev/null || true
sleep 3
wait $STRACE_PID 2>/dev/null || true
echo "[REST] strace capture complete."

sleep 5

########################################
# gRPC
########################################
echo ""
echo "[gRPC] Locating server process on port 50051..."
GRPC_PID=$(get_worker_pid 50051)
if [ -z "$GRPC_PID" ]; then
    echo "ERROR: gRPC server not found on port 50051."
    echo "Start with: python3 servers/grpc_server.py"
    exit 1
fi
echo "[gRPC] Attaching strace to PID $GRPC_PID"

# Warmup
"$ROOT_DIR/.venv/bin/python3" - <<EOF > /dev/null 2>&1
import sys, grpc
sys.path.insert(0, '$ROOT_DIR/payload_gen')
import schema_pb2, schema_pb2_grpc
ch = grpc.insecure_channel('127.0.0.1:50051')
stub = schema_pb2_grpc.BenchmarkServiceStub(ch)
stub.ProcessTransaction(schema_pb2.Transaction(transaction_id='w', timestamp=1.0, user_id=1, amount=1.0, currency='USD', description='w', merchant_code='W', metadata='x'), timeout=5)
EOF

rm -f "$GRPC_STRACE"
strace -f -c -p "$GRPC_PID" 2>"$GRPC_STRACE" &
STRACE_PID=$!
sleep 2

echo "[gRPC] Sending $N requests..."
"$ROOT_DIR/.venv/bin/python3" - <<EOF
import sys, grpc, time
sys.path.insert(0, '$ROOT_DIR/payload_gen')
import schema_pb2, schema_pb2_grpc
from generator import PAYLOAD_10KB

ch = grpc.insecure_channel('127.0.0.1:50051')
stub = schema_pb2_grpc.BenchmarkServiceStub(ch)
req = schema_pb2.Transaction(**PAYLOAD_10KB)

for i in range(1, $N + 1):
    try:
        stub.ProcessTransaction(req, timeout=10)
    except Exception as e:
        print(f"Error {i}: {e}", file=sys.stderr)
    if i % 200 == 0:
        print(f"  {i}/$N sent", file=sys.stderr)
EOF

sleep 1
kill -INT $STRACE_PID 2>/dev/null || true
sleep 3
wait $STRACE_PID 2>/dev/null || true
echo "[gRPC] strace capture complete."

########################################
# Results — print all 3 strace summaries
########################################
echo ""
echo "==================== PILLAR 4 RESULTS ====================="
echo ""
echo "TCP syscall summary (1000 requests, PID $TCP_PID) — Speed-of-Light Baseline:"
if [ -s "$TCP_STRACE" ]; then
    cat "$TCP_STRACE"
else
    echo "  ERROR: $TCP_STRACE is empty"
fi

echo ""
echo "REST syscall summary (1000 requests, PID $REST_PID):"
if [ -s "$REST_STRACE" ]; then
    cat "$REST_STRACE"
else
    echo "  ERROR: $REST_STRACE is empty"
fi

echo ""
echo "gRPC syscall summary (1000 requests, PID $GRPC_PID):"
if [ -s "$GRPC_STRACE" ]; then
    cat "$GRPC_STRACE"
else
    echo "  ERROR: $GRPC_STRACE is empty"
fi

echo ""
echo "==========================================================="
echo "Key metrics: total syscall count relative to TCP baseline."
echo "Timing columns from strace are NOT used (ptrace overhead)."
echo ""
echo "Next step: python3 benchmarks/parse_results.py"
