import socket
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from payload_gen.generator import PAYLOAD_10KB
import json

def run_tcp_benchmark(requests=10000):
    host = '127.0.0.1'
    port = 9000
    
    # Pre-encode payload just to test network/OS, not serialization
    data = json.dumps(PAYLOAD_10KB).encode('utf-8')
    data_len = len(data)
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
    except Exception as e:
        print(f"Failed to connect to TCP server: {e}")
        return

    print(f"Blasting {requests} requests to pure TCP/IP socket...")
    latencies = []
    
    # For a true raw test, we'll send sequentially to measure raw round-trip minimums
    start_total = time.perf_counter()
    for _ in range(requests):
        t0 = time.perf_counter()
        s.sendall(data)
        # Wait for echo
        received = 0
        while received < data_len:
            packet = s.recv(4096)
            if not packet: break
            received += len(packet)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000) # strictly in ms
        
    end_total = time.perf_counter()
    s.close()
    
    duration = end_total - start_total
    latencies.sort()
    p99 = latencies[int(requests * 0.99)]
    avg = sum(latencies) / len(latencies)
    
    print(f"\n--> TCP/IP BASELINE:")
    print(f"Total Time: {duration:.2f}s | RPS: {(requests/duration):.2f}")
    print(f"Avg Latency:  {avg:.2f}ms")
    print(f"P99 Latency:  {p99:.2f}ms")

if __name__ == "__main__":
    run_tcp_benchmark()
