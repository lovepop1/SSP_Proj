#!/bin/bash
# Pillar 2: Wire Efficiency
# Captures actual bytes on the loopback interface for 200 requests each.
# Uses tshark to sum frame.len (actual wire bytes, not pcap file size).
# Requires: tshark, sudo, both servers running.

set -e

REST_URL="http://127.0.0.1:8000"
GRPC_HOST="127.0.0.1:50051"
REST_PCAP="/tmp/p2_rest.pcap"
GRPC_PCAP="/tmp/p2_grpc.pcap"
N=200

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Pillar 2: Wire Efficiency Benchmark ($N requests per protocol)"
echo "=============================================================="

# Verify tshark is available
if ! command -v tshark &>/dev/null; then
    echo "ERROR: tshark not found. Install with: sudo apt-get install -y tshark"
    exit 1
fi

rm -f "$REST_PCAP" "$GRPC_PCAP"

########################################
# REST CAPTURE
########################################
echo ""
echo "[REST] Starting tcpdump capture on port 8000..."
sudo tcpdump -i lo -w "$REST_PCAP" 'port 8000' 2>/dev/null &
TCPDUMP_PID=$!
sleep 2

echo "[REST] Sending $N requests..."
"$ROOT_DIR/.venv/bin/python3" - <<EOF
import sys, requests
sys.path.insert(0, '$ROOT_DIR/payload_gen')
from generator import PAYLOAD_10KB
import json

session = requests.Session()
headers = {"Content-Type": "application/json"}
body = json.dumps(PAYLOAD_10KB)

for i in range($N):
    try:
        session.post('http://127.0.0.1:8000/transaction', data=body, headers=headers, timeout=10)
    except Exception as e:
        print(f"Error {i}: {e}", file=sys.stderr)
print("REST requests done")
EOF

sleep 2
sudo kill $TCPDUMP_PID 2>/dev/null
wait $TCPDUMP_PID 2>/dev/null
echo "[REST] Capture complete."

########################################
# gRPC CAPTURE
########################################
echo ""
echo "[gRPC] Starting tcpdump capture on port 50051..."
sudo tcpdump -i lo -w "$GRPC_PCAP" 'port 50051' 2>/dev/null &
TCPDUMP_PID=$!
sleep 2

echo "[gRPC] Sending $N requests..."
"$ROOT_DIR/.venv/bin/python3" - <<EOF
import sys, grpc
sys.path.insert(0, '$ROOT_DIR/payload_gen')
import schema_pb2, schema_pb2_grpc
from generator import PAYLOAD_10KB

channel = grpc.insecure_channel('127.0.0.1:50051')
stub = schema_pb2_grpc.BenchmarkServiceStub(channel)
req = schema_pb2.Transaction(**PAYLOAD_10KB)

for i in range($N):
    try:
        stub.ProcessTransaction(req, timeout=10)
    except Exception as e:
        print(f"Error {i}: {e}", file=sys.stderr)
print("gRPC requests done")
EOF

sleep 2
sudo kill $TCPDUMP_PID 2>/dev/null
wait $TCPDUMP_PID 2>/dev/null
echo "[gRPC] Capture complete."

########################################
# ANALYSIS — tshark sums actual frame bytes
########################################
echo ""
echo "Analyzing wire bytes with tshark..."

REST_WIRE=$(tshark -r "$REST_PCAP" -T fields -e frame.len 2>/dev/null | awk '{sum+=$1} END {print sum}')
GRPC_WIRE=$(tshark -r "$GRPC_PCAP" -T fields -e frame.len 2>/dev/null | awk '{sum+=$1} END {print sum}')

REST_AVG=$(awk "BEGIN {printf \"%.0f\", $REST_WIRE / $N}")
GRPC_AVG=$(awk "BEGIN {printf \"%.0f\", $GRPC_WIRE / $N}")

echo ""
echo "==================== PILLAR 2 RESULTS ===================="
echo ""
echo "REST  — total wire bytes: $REST_WIRE  |  avg per request: $REST_AVG bytes"
echo "gRPC  — total wire bytes: $GRPC_WIRE  |  avg per request: $GRPC_AVG bytes"
echo ""
echo "Wire overhead vs 10240-byte payload:"
echo "  REST overhead : $(( REST_AVG - 10240 )) bytes/request"
echo "  gRPC overhead : $(( GRPC_AVG - 10240 )) bytes/request"
echo "==========================================================="

# Save summary for parse_results.py to consume without re-running tshark
SUMMARY="$SCRIPT_DIR/pillar2_out.txt"
{
    echo "REST  — total wire bytes: $REST_WIRE  |  avg per request: $REST_AVG bytes"
    echo "gRPC  — total wire bytes: $GRPC_WIRE  |  avg per request: $GRPC_AVG bytes"
} > "$SUMMARY"
echo ""
echo "Summary saved to $SUMMARY"
