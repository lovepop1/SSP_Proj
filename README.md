# Multi-Layer Performance Breakdown: System & Protocol Overheads

This repository contains a comprehensive empirical benchmarking suite designed to isolate and quantify the "architectural tax" levied by different communication paradigms on the Linux (WSL2) network stack.

## 🏗️ The Four-Pillar Methodology

We evaluate five communication technologies—**Raw TCP/IP, REST (FastAPI), gRPC, Apache Kafka, and RabbitMQ**—across four distinct layers of the system:

1.  **Pillar 1: Throughput & Tail Latency** - Measures RPS and P99 latency under concurrent load, categorized by Synchronous vs. Asynchronous architectures.
2.  **Pillar 2: Payload Efficiency (Wire Bloat)** - Uses `tcpdump` and `tshark` to measure actual bytes on the wire, quantifying the overhead of HTTP headers, JSON verbosity, and binary framing.
3.  **Pillar 3: Serialization CPU Cost** - Direct user-space profiling of JSON vs. Protobuf encoding to measure CPU-bound bottlenecking.
4.  **Pillar 4: Kernel-Space Syscall Overhead** - Uses `strace -f -c` to count the exact number of context switches and kernel entries (I/O, Polling, Locking) per request.

---

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install System Tools
sudo apt-get update && sudo apt-get install -y tcpdump tshark strace wrk lsof
```

### 2. Generate Protobuf Bindings
```bash
python3 generate_grpc.py
```

### 3. Run the Servers
It is recommended to run each server in a dedicated terminal:
*   `python3 servers/tcp_server.py` (Port 9000)
*   `python3 servers/rest_server.py` (Port 8000)
*   `python3 servers/grpc_server.py` (Port 50051)

---

## 📊 Benchmarking Commands

### Pillar 1: Throughput & Latency
Run the automated load tests for synchronous protocols:
```bash
bash benchmarks/pillar1_latency.sh
```

### Pillar 2: Empirical Wire Measurement (Critical Fix 1)
To capture actual network bytes (including the TCP "Speed of Light" baseline):
```bash
sudo bash benchmarks/measure_tcp_wire.sh
sudo bash benchmarks/pillar2_wire.sh
```

### Pillar 3: CPU Serialization Analysis
```bash
python3 benchmarks/pillar3_cpu.py
```

### Pillar 4: Kernel Syscall Tracing
```bash
sudo bash benchmarks/pillar4_syscalls.sh
```

---

## 📈 Key Insights & "Sure" Results

### 1. The gRPC Anomaly (Python Library Tax)
Our results show gRPC recording significantly lower RPS (489) than REST (1,755). This is **not a protocol failure**. It is a measured **Implementation Tax** of the Python `grpcio` library, which uses a C-extension threading model that conflicts with the Python GIL. In contrast, Pillar 3 shows that the **Protobuf format is 15.0x faster** than JSON at the serialization layer.

### 2. The Asynchronous Shock Absorbers
Kafka and RabbitMQ results are categorized separately. 
*   **Kafka (1,209ms P50)** is not "slow"; it is **Disk Durable**. Every millisecond represents a crash-safety guarantee.
*   **RabbitMQ (21,656 RPS)** demonstrates the power of in-memory buffering for non-persistent task queues.

### 3. The Syscall Explosion
Pillar 4 reveals the "Hidden Tax" of frameworks:
*   **Raw TCP:** 2,015 syscalls / 1,000 requests (Pure I/O).
*   **REST:** 6,179 syscalls (Event-loop polling via `epoll_wait`).
*   **gRPC/Python:** 48,125 syscalls (Dominated by `futex` mutex contention).

---

## 🖼️ Visualizations
Generated plots are stored in `figures/`:
1.  `fig1_rps_comparison.png` - Overall throughput.
2.  `fig2_tail_latency.png` - Synchronous P99 spikes.
3.  `fig3_wire_bloat.png` - Header/Metadata overhead.
4.  `fig4_serialization.png` - User-space CPU budget.
5.  `fig5_syscall_overhead.png` - Kernel-space transition counts.
6.  `fig6_broker_latency.png` - **Broker-Specific Analysis** (Log-scale comparison of Kafka vs. RabbitMQ).

---

## 🛠️ Hardware & OS Isolation
*   **Host:** x86_64 Physical Host.
*   **Kernel:** Linux (WSL2 / Ubuntu 22.04).
*   **Isolation:** All tests conducted via `lo` (Loopback) to isolate software stack overhead from network hardware jitter.
