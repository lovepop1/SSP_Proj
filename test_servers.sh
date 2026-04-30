#!/bin/bash
cd '/mnt/c/Users/Aditya Nangarath/Desktop/ssp_proj'
source .venv/bin/activate
python3 servers/rest_server.py > rest_test.log 2>&1 &
RPID=$!
python3 servers/grpc_server.py > grpc_test.log 2>&1 &
GPID=$!
sleep 3
kill $RPID $GPID || true
