#!/bin/bash
cd '/mnt/c/Users/Aditya Nangarath/Desktop/ssp_proj'
source .venv/bin/activate

echo "-----------------------------------"
echo "RUNNING PILLAR 1 (REST Latency)"
python3 servers/rest_server.py > /dev/null 2>&1 &
REST_PID=$!
sleep 8
wrk -t2 -c10 -d10s -s benchmarks/scripts/post.lua http://127.0.0.1:8000/transaction > benchmarks/rest_10.txt
cat benchmarks/rest_10.txt
kill $REST_PID

echo "-----------------------------------"
echo "RUNNING PILLAR 1 (gRPC Latency)"
python3 servers/grpc_server.py > /dev/null 2>&1 &
GRPC_PID=$!
sleep 8
PAYLOAD=$(python3 -c "print('X'*10000)")
ghz --insecure --proto payload_gen/schema.proto --call payload_gen.BenchmarkService/ProcessTransaction -c 10 -n 100000 -d '{"transaction_id":"123","timestamp":1.0,"user_id":1,"amount":10.0,"currency":"USD","description":"x","merchant_code":"M","metadata":"'$PAYLOAD'"}' 127.0.0.1:50051 > benchmarks/grpc_10.txt
cat benchmarks/grpc_10.txt
kill $GRPC_PID
