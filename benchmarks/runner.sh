#!/bin/bash
# Master Benchmark Orchestrator (Run inside WSL)

echo "=== Installing benchmarking tools ==="
sudo apt-get update
sudo apt-get install -y wrk strace tcpdump
if ! command -v ghz &> /dev/null; then
    echo "Installing ghz (gRPC load tester)..."
    wget https://github.com/bojand/ghz/releases/download/v0.120.0/ghz-linux-x86_64.tar.gz
    tar -xzf ghz-linux-x86_64.tar.gz
    sudo mv ghz /usr/local/bin/
    rm ghz-linux-x86_64.tar.gz
fi
echo "Tools installed successfully."

echo "
=========================================================
      THE 4-PILLAR BENCHMARKING EXECUTION GUIDE
=========================================================
Execute these benchmarks in isolated terminals to ensure 
CPU context-switching doesn't invalidate your results.

--- PILLAR 1: Load & Latency ---
REST:
  wrk -t2 -c100 -d60s -s scripts/post.lua http://localhost:8000/transaction

gRPC:
  # The JSON string below gets converted transparently to binary protobuf by ghz
  ghz --insecure --proto ../payload_gen/schema.proto --call payload_gen.BenchmarkService/ProcessTransaction -c 100 -n 100000 -d '{\"transaction_id\":\"123\",\"timestamp\":1.0,\"user_id\":1,\"amount\":10.0,\"currency\":\"USD\",\"description\":\"x\",\"merchant_code\":\"M\",\"metadata\":\"'$(printf 'X%.0s' {1..10000})'\"}' localhost:50051

Kafka:
  kafka-producer-perf-test --topic test_topic --num-records 10000 --record-size 10240 --throughput -1 --producer-props bootstrap.servers=localhost:9092

RabbitMQ:
  rabbitmq-perf-test --uri amqp://guest:guest@localhost:5672 --size 10240 --producers 10 --consumers 0 --time 60


--- PILLAR 2: Network Efficiency (Wire Bloat) ---
1. Start your chosen server.
2. Monitor loopback: 
   sudo tcpdump -i lo port 8000 -w REST_traffic.pcap 
3. Send requests.
4. Stop tcpdump. 
   ls -lh REST_traffic.pcap
   # Average wire-bytes per request = (Total pcap size) / (Number of requests)


--- PILLAR 3: User-Space CPU Serialization ---
source ../.venv/bin/activate
python3 pillar3_cpu.py


--- PILLAR 4: Kernel System Calls Overhead ---
1. Start your chosen server normally (e.g. REST).
2. Get its process ID: 
   PID=\$(pgrep -f rest_server.py)
   sudo strace -c -p \$PID -o syscalls_rest.log
3. Blast exactly 1000 requests to it from another terminal.
4. Kill the server, then read `syscalls_rest.log`.
   Pay attention to `epoll_wait` and `write` counts.
=========================================================
"
