#!/bin/bash
# benchmarks/measure_tcp_wire.sh
# Critical Fix 1: Empirical measurement of TCP wire overhead

set -e

# Ensure sudo access upfront so background processes don't block on password prompt
echo "This script requires sudo for tcpdump. Please enter your password if prompted:"
sudo -v

# Configuration
PORT=9000
N=200
PCAP_FILE="/tmp/tcp_baseline_empirical.pcap"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Step 1: Ensuring TCP Server is running..."
if ! lsof -i :$PORT > /dev/null; then
    echo "Starting TCP Server..."
    nohup "$ROOT_DIR/.venv/bin/python3" "$ROOT_DIR/servers/tcp_server.py" > /dev/null 2>&1 &
    SERVER_PID=$!
    sleep 2
else
    echo "TCP Server already running."
fi

echo "Step 2: Starting tcpdump capture on loopback..."
sudo tcpdump -i lo -w "$PCAP_FILE" "port $PORT" 2>/dev/null &
TCPDUMP_PID=$!
sleep 2

echo "Step 3: Running TCP client for $N requests..."
"$ROOT_DIR/.venv/bin/python3" - <<EOF
import sys, os
sys.path.append('$ROOT_DIR')
from benchmarks.tcp_client import run_tcp_benchmark
run_tcp_benchmark(requests=$N)
EOF

sleep 2

echo "Step 4: Stopping capture..."
sudo kill $TCPDUMP_PID 2>/dev/null
wait $TCPDUMP_PID 2>/dev/null

echo "Step 5: Analyzing results with tshark..."
TOTAL_BYTES=$(tshark -r "$PCAP_FILE" -T fields -e frame.len 2>/dev/null | awk '{sum+=$1} END {print sum}')
AVG_BYTES=$(awk "BEGIN {printf \"%.0f\", $TOTAL_BYTES / $N}")

echo "----------------------------------------------------------"
echo "Empirical TCP Baseline Results ($N requests):"
echo "Total Wire Bytes: $TOTAL_BYTES"
echo "Average per Request: $AVG_BYTES bytes"
echo "----------------------------------------------------------"

# Optional: cleanup
# [ "$SERVER_PID" ] && kill $SERVER_PID
