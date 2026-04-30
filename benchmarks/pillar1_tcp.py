"""
Pillar 1: TCP Baseline Throughput & Tail Latency
- Raw TCP/IP socket, no application protocol overhead
- 10 concurrent connections, 60 second duration, 10KB payload
- Each connection sends requests sequentially and measures round-trip time
- Results saved to benchmarks/tcp_out.txt

Usage:
  python3 benchmarks/pillar1_tcp.py
  python3 benchmarks/pillar1_tcp.py --host 127.0.0.1 --port 9000 --duration 60 --concurrency 10
"""

import socket
import threading
import time
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'payload_gen'))
from generator import PAYLOAD_10KB

PAYLOAD_BYTES = json.dumps(PAYLOAD_10KB).encode('utf-8')
PAYLOAD_SIZE  = len(PAYLOAD_BYTES)


def worker(host, port, duration, results, idx):
    """Single connection worker: sends payload, reads echo, records latency."""
    latencies = []
    errors    = 0
    count     = 0

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.settimeout(5.0)
    except Exception as e:
        results[idx] = {'latencies': [], 'errors': 1, 'count': 0}
        return

    deadline = time.perf_counter() + duration

    while time.perf_counter() < deadline:
        try:
            t0 = time.perf_counter()
            sock.sendall(PAYLOAD_BYTES)

            # Read until we get the full echo back
            received = 0
            while received < PAYLOAD_SIZE:
                chunk = sock.recv(PAYLOAD_SIZE - received)
                if not chunk:
                    raise ConnectionError("Server closed connection")
                received += len(chunk)

            latencies.append((time.perf_counter() - t0) * 1000)  # ms
            count += 1
        except Exception:
            errors += 1
            # Reconnect on error
            try:
                sock.close()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
                sock.settimeout(5.0)
            except Exception:
                break

    sock.close()
    results[idx] = {'latencies': latencies, 'errors': errors, 'count': count}


def percentile(sorted_data, p):
    if not sorted_data:
        return None
    idx = int(len(sorted_data) * p / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def run(host, port, duration, concurrency, out_path):
    print(f"Pillar 1: TCP Baseline Throughput & Tail Latency")
    print(f"=================================================")
    print(f"Host: {host}:{port}  |  Concurrency: {concurrency}  |  Duration: {duration}s  |  Payload: {PAYLOAD_SIZE} bytes")
    print()

    # Verify server is up
    try:
        test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test.settimeout(3)
        test.connect((host, port))
        test.close()
        print(f"TCP server OK")
    except Exception:
        print(f"ERROR: TCP server not responding on {host}:{port}")
        print(f"Start with: python3 servers/tcp_server.py")
        sys.exit(1)

    # Warmup — 1 connection, 100 requests
    print("Warming up...")
    warmup_results = [None]
    t = threading.Thread(target=worker, args=(host, port, 2, warmup_results, 0))
    t.start()
    t.join()

    # Main benchmark
    print(f"Running {concurrency} concurrent connections for {duration}s...")
    results = [None] * concurrency
    threads = []
    t_start = time.perf_counter()

    for i in range(concurrency):
        t = threading.Thread(target=worker, args=(host, port, duration, results, i))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.perf_counter() - t_start

    # Aggregate
    all_latencies = []
    total_requests = 0
    total_errors   = 0

    for r in results:
        if r:
            all_latencies.extend(r['latencies'])
            total_requests += r['count']
            total_errors   += r['errors']

    all_latencies.sort()
    rps     = total_requests / elapsed
    avg_ms  = sum(all_latencies) / len(all_latencies) if all_latencies else 0
    p50     = percentile(all_latencies, 50)
    p75     = percentile(all_latencies, 75)
    p90     = percentile(all_latencies, 90)
    p99     = percentile(all_latencies, 99)

    output = (
        f"\nTCP Baseline Results ({concurrency} connections, {duration}s, {PAYLOAD_SIZE}B payload)\n"
        f"{'='*60}\n"
        f"Total requests : {total_requests:,}\n"
        f"Total errors   : {total_errors}\n"
        f"Elapsed        : {elapsed:.2f}s\n"
        f"Requests/sec   : {rps:,.2f}\n"
        f"Avg latency    : {avg_ms:.2f} ms\n"
        f"P50 latency    : {p50:.2f} ms\n"
        f"P75 latency    : {p75:.2f} ms\n"
        f"P90 latency    : {p90:.2f} ms\n"
        f"P99 latency    : {p99:.2f} ms\n"
    )

    print(output)

    with open(out_path, 'w') as f:
        f.write(output)
    print(f"Results saved to {out_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',        default='127.0.0.1')
    parser.add_argument('--port',        type=int, default=9000)
    parser.add_argument('--duration',    type=int, default=60)
    parser.add_argument('--concurrency', type=int, default=10)
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path   = os.path.join(script_dir, 'tcp_out.txt')

    run(args.host, args.port, args.duration, args.concurrency, out_path)
