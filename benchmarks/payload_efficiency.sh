#!/bin/bash

echo "📡 Payload Efficiency Benchmark (100 requests - Network Size Analysis)"
echo "=================================================================="

REST_PCAP="/tmp/rest_capture.pcap"
GRPC_PCAP="/tmp/grpc_capture.pcap"

# Clean old files
rm -f $REST_PCAP $GRPC_PCAP

#############################################
# STEP 1: Compute ACTUAL payload sizes
#############################################

echo ""
echo "🧮 Computing actual payload sizes..."

REST_REQUEST_SIZE=$(./.venv/bin/python3 - <<EOF
import json
from payload_generator import generate_10kb_payload
payload = generate_10kb_payload()
print(len(json.dumps(payload).encode()))
EOF
)

REST_RESPONSE_SIZE=100  # approx

GRPC_REQUEST_SIZE=$(./.venv/bin/python3 - <<EOF
from payload_generator import generate_10kb_payload
payload = generate_10kb_payload()
print(len(payload["padding"]) + 100)
EOF
)

GRPC_RESPONSE_SIZE=60  # approx

NUM_REQUESTS=100

REST_TOTAL_PAYLOAD=$(( (REST_REQUEST_SIZE + REST_RESPONSE_SIZE) * NUM_REQUESTS ))
GRPC_TOTAL_PAYLOAD=$(( (GRPC_REQUEST_SIZE + GRPC_RESPONSE_SIZE) * NUM_REQUESTS ))

echo "REST payload per request: $REST_REQUEST_SIZE + $REST_RESPONSE_SIZE"
echo "gRPC payload per request: $GRPC_REQUEST_SIZE + $GRPC_RESPONSE_SIZE"

#############################################
# STEP 2: REST CAPTURE
#############################################

echo ""
echo "🔍 Capturing REST traffic..."

sudo -v
sudo tcpdump -i lo -w $REST_PCAP 'port 8080' &
TCPDUMP_REST_PID=$!

sleep 3

echo "Sending REST requests..."

./.venv/bin/python3 - <<EOF > /dev/null
import requests
import sys
sys.path.append('.')
from payload_generator import generate_10kb_payload

session = requests.Session()
payload = generate_10kb_payload()
headers = {"Content-Type": "application/json"}

for i in range(100):
    try:
        session.post('http://localhost:8080/api/transaction', json=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"Error on request {i}: {e}", file=sys.stderr)
EOF

sleep 3
sudo kill $TCPDUMP_REST_PID
wait $TCPDUMP_REST_PID 2>/dev/null

echo "✅ REST capture complete"

#############################################
# STEP 3: gRPC CAPTURE (FIXED)
#############################################

echo ""
echo "🔍 Capturing gRPC traffic..."

sudo -v
sudo tcpdump -i lo -w $GRPC_PCAP 'port 50051' &
TCPDUMP_GRPC_PID=$!

sleep 3

echo "Sending gRPC requests..."

# ✅ FIX: reuse channel + stub
./.venv/bin/python3 - <<EOF > /dev/null
import grpc
import sys
sys.path.append('.')
import transaction_pb2
import transaction_pb2_grpc
from payload_generator import generate_10kb_payload

channel = grpc.insecure_channel('localhost:50051')
stub = transaction_pb2_grpc.TransactionServiceStub(channel)

for i in range(100):
    try:
        payload = generate_10kb_payload()

        request = transaction_pb2.Transaction(
            transaction_id=payload['transaction_id'],
            timestamp=payload['timestamp'],
            user_id=payload['user_id'],
            event_type=payload['event_type'],
            amount=payload['amount'],
            padding=payload['padding']
        )

        response = stub.ProcessTransaction(request, timeout=5)

    except Exception as e:
        print(f"gRPC Error on request {i}: {e}", file=sys.stderr)
EOF

sleep 3
sudo kill $TCPDUMP_GRPC_PID
wait $TCPDUMP_GRPC_PID 2>/dev/null

echo "✅ gRPC capture complete"

#############################################
# STEP 4: ANALYSIS (TOTAL BYTES)
#############################################

echo ""
echo "📊 Analyzing total bytes..."

REST_TOTAL_BYTES=$(wc -c < $REST_PCAP)
GRPC_TOTAL_BYTES=$(wc -c < $GRPC_PCAP)

#############################################
# STEP 5: PAYLOAD EFFICIENCY
#############################################

REST_EFF=$(awk "BEGIN {printf \"%.2f\", ($REST_TOTAL_PAYLOAD/$REST_TOTAL_BYTES)*100}")
GRPC_EFF=$(awk "BEGIN {printf \"%.2f\", ($GRPC_TOTAL_PAYLOAD/$GRPC_TOTAL_BYTES)*100}")

#############################################
# STEP 6: OUTPUT
#############################################

echo ""
echo "================ FINAL RESULTS ================"
echo ""

echo "🔵 REST Results:"
echo "   Total Payload Bytes: $REST_TOTAL_PAYLOAD"
echo "   Total Captured Bytes: $REST_TOTAL_BYTES"
echo "   Payload Efficiency: $REST_EFF %"

echo ""
echo "🟢 gRPC Results:"
echo "   Total Payload Bytes: $GRPC_TOTAL_PAYLOAD"
echo "   Total Captured Bytes: $GRPC_TOTAL_BYTES"
echo "   Payload Efficiency: $GRPC_EFF %"

echo ""
echo "📈 Key Insight:"
echo "Payload efficiency = useful data / total network cost"
echo ""
echo "Files:"
echo "   $REST_PCAP"
echo "   $GRPC_PCAP"