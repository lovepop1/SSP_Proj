"""
parse_results.py — extracts benchmark metrics from raw tool output files
and writes a single results.json consumed by visualizations/plot_results.py.

Parses:
  benchmarks/rest_10.txt        — wrk output (Pillar 1 REST)
  benchmarks/grpc_10.txt        — ghz output (Pillar 1 gRPC)
  benchmarks/kafka_out.txt      — kafka-producer-perf-test output (Pillar 1 Kafka)
  benchmarks/rabbitmq_out.txt   — rabbitmq-perf-test output (Pillar 1 RabbitMQ)
  benchmarks/pillar3_out.txt    — pillar3_cpu.py stdout (Pillar 3)
  benchmarks/pillar2_out.txt    — pillar2_wire.sh summary (Pillar 2)
  /tmp/p4_rest_strace.txt       — strace -c output (Pillar 4 REST)
  /tmp/p4_grpc_strace.txt       — strace -c output (Pillar 4 gRPC)

Usage:
  python3 benchmarks/parse_results.py
  python3 benchmarks/parse_results.py --out results/results.json
"""

import re, json, sys, os, argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)


def parse_wrk(path):
    """Parse wrk --latency output for REST metrics."""
    text = open(path).read()

    def find(pattern, flags=0, default=None):
        m = re.search(pattern, text, flags)
        return float(m.group(1)) if m else default

    def latency_ms(pattern, flags=0):
        m = re.search(pattern, text, flags)
        if not m:
            return None
        val, unit = float(m.group(1)), m.group(2)
        if unit == 'us': return val / 1000
        if unit == 'ms': return val
        if unit == 's':  return val * 1000
        return val

    rps = find(r'Requests/sec:\s+([\d.]+)')
    avg = latency_ms(r'^\s+Latency\s+([\d.]+)(us|ms|s)', re.MULTILINE)
    p50 = latency_ms(r'50(?:\.000)?%\s+([\d.]+)(us|ms|s)')
    p75 = latency_ms(r'75(?:\.000)?%\s+([\d.]+)(us|ms|s)')
    p90 = latency_ms(r'90(?:\.000)?%\s+([\d.]+)(us|ms|s)')
    p95 = latency_ms(r'95(?:\.000)?%\s+([\d.]+)(us|ms|s)')
    p99 = latency_ms(r'99(?:\.000)?%\s+([\d.]+)(us|ms|s)')

    return {
        "rps": rps, "avg_ms": avg,
        "p50_ms": p50, "p75_ms": p75,
        "p90_ms": p90, "p95_ms": p95, "p99_ms": p99,
    }


def parse_ghz(path):
    """Parse ghz text output for gRPC metrics."""
    text = open(path).read()

    def find(pattern, default=None):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else default

    rps = find(r'Requests/sec:\s+([\d.]+)')
    avg = find(r'Average:\s+([\d.]+)\s*ms')
    p50 = find(r'50\s*%\s+in\s+([\d.]+)\s*ms')
    p75 = find(r'75\s*%\s+in\s+([\d.]+)\s*ms')
    p90 = find(r'90\s*%\s+in\s+([\d.]+)\s*ms')
    p95 = find(r'95\s*%\s+in\s+([\d.]+)\s*ms')
    p99 = find(r'99\s*%\s+in\s+([\d.]+)\s*ms')

    return {
        "rps": rps, "avg_ms": avg,
        "p50_ms": p50, "p75_ms": p75,
        "p90_ms": p90, "p95_ms": p95, "p99_ms": p99,
    }


def parse_pillar3(path):
    """Parse pillar3_cpu.py stdout for serialization metrics."""
    if not os.path.exists(path):
        return {}
    text = open(path).read()

    def find(pattern, default=None):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else default

    return {
        "json_total_s":    find(r'JSON\s+total:\s+([\d.]+)s'),
        "proto_total_s":   find(r'Proto total:\s+([\d.]+)s'),
        "json_us_op":      find(r'JSON\s+total:.*?avg:\s+([\d.]+)\s*µs/op'),
        "proto_us_op":     find(r'Proto total:.*?avg:\s+([\d.]+)\s*µs/op'),
        "json_share_pct":  find(r'JSON\s+total:.*?share:\s+([\d.]+)%'),
        "proto_share_pct": find(r'Proto total:.*?share:\s+([\d.]+)%'),
        "speedup":         find(r'Speedup: Protobuf is ([\d.]+)x faster'),
        "json_size_bytes": find(r'JSON\s+serialized size:\s+(\d+)\s+bytes'),
        "proto_size_bytes":find(r'Proto serialized size:\s+(\d+)\s+bytes'),
    }


def parse_strace(path):
    """
    Parse strace -c output captured via 2>file.

    IMPORTANT: strace -c OMITS the 'errors' column entirely when a syscall
    has zero errors, producing only 5 columns:
      % time  seconds  usecs/call  calls  syscall
    When errors are present, 6 columns appear:
      % time  seconds  usecs/call  calls  errors  syscall

    The previous version required >= 6 parts and skipped all zero-error rows,
    meaning TCP (all zero-error syscalls) was never parsed at all.
    This version handles both layouts.

    Timing columns are intentionally discarded (ptrace overhead inflates them).
    """
    if not os.path.exists(path):
        return {}

    text = open(path).read()
    result = {}
    total_calls = 0
    total_errors = 0

    for line in text.splitlines():
        line = line.strip()
        # Skip header, separator, and strace attach/detach lines
        if not line or line.startswith('%') or line.startswith('-'):
            continue
        if line.startswith('strace:'):
            continue

        parts = line.split()

        # 5-column row: pct seconds usecs/call calls syscall  (no error column)
        if len(parts) == 5:
            try:
                calls  = int(parts[3])
                errors = 0
                name   = parts[4]
            except (ValueError, IndexError):
                continue

        # 6-column row: pct seconds usecs/call calls errors syscall
        elif len(parts) >= 6:
            try:
                calls  = int(parts[3])
                errors = int(parts[4])
                name   = parts[5]
            except (ValueError, IndexError):
                continue

        else:
            continue

        if name == 'total':
            total_calls  = calls
            total_errors = errors
        else:
            result[name] = calls
            if errors:
                result.setdefault('_errors', {})[name] = errors

    if not result and total_calls == 0:
        return {}

    out = {"total_calls": total_calls, "errors": total_errors}
    out.update({k: v for k, v in result.items() if not k.startswith('_')})
    return out


def parse_kafka(path):
    """
    Parse kafka-producer-perf-test output.

    Final summary line is the only line containing percentile data:
      100000 records sent, 1664.198106 records/sec (16.25 MB/sec),
        1205.35 ms avg latency, 1892.00 ms max latency,
        1209 ms 50th, 1574 ms 95th, 1756 ms 99th, 1879 ms 99.9th.
    """
    if not os.path.exists(path):
        return {}
    text = open(path).read()

    # Match only lines that contain percentile markers (50th, 95th, 99th)
    # These only appear on the final summary line, not intermediate progress lines
    for line in text.splitlines():
        if '50th' not in line or '99th' not in line:
            continue
        m = re.search(
            r'(\d+)\s+records sent,\s+([\d.]+)\s+records/sec'
            r'.*?([\d.]+)\s+ms avg latency,\s+([\d.]+)\s+ms max latency'
            r'.*?(\d+)\s+ms 50th,\s+(\d+)\s+ms 95th,\s+(\d+)\s+ms 99th',
            line
        )
        if m:
            return {
                "records_sent": int(m.group(1)),
                "rps":          float(m.group(2)),
                "avg_ms":       float(m.group(3)),
                "max_ms":       float(m.group(4)),
                "p50_ms":       float(m.group(5)),
                "p95_ms":       float(m.group(6)),
                "p99_ms":       float(m.group(7)),
            }
    return {}


def parse_rabbitmq(path):
    """
    Parse rabbitmq-perf-test output.

    The tool prints periodic per-second lines AND a final aggregate summary:
      id: test-xxx, sending rate avg: 26063 msg/s
      id: test-xxx, receiving rate avg: 26063 msg/s
      id: test-xxx, consumer latency min/median/75th/95th/99th/max 299/2286/3477/5894/8528/32890 µs

    We use the final aggregate lines for stable end-of-run values.
    Falls back to last periodic line if aggregate is absent.
    """
    if not os.path.exists(path):
        return {}
    text = open(path).read()

    # Try final aggregate summary lines first
    send_avg = re.search(r'sending rate avg:\s+([\d.]+)\s+msg/s', text)
    recv_avg = re.search(r'receiving rate avg:\s+([\d.]+)\s+msg/s', text)
    lat_agg  = re.search(
        r'consumer latency min/median/75th/95th/99th/max\s+'
        r'([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*µs',
        text
    )

    if send_avg and lat_agg:
        us_to_ms = lambda x: round(float(x) / 1000, 3)
        return {
            "send_rate_rps": float(send_avg.group(1)),
            "recv_rate_rps": float(recv_avg.group(1)) if recv_avg else float(send_avg.group(1)),
            "min_ms":        us_to_ms(lat_agg.group(1)),
            "p50_ms":        us_to_ms(lat_agg.group(2)),
            "p75_ms":        us_to_ms(lat_agg.group(3)),
            "p95_ms":        us_to_ms(lat_agg.group(4)),
            "p99_ms":        us_to_ms(lat_agg.group(5)),
            "max_ms":        us_to_ms(lat_agg.group(6)),
        }

    # Fallback: last periodic line
    pattern = re.compile(
        r'sent:\s+([\d.]+)\s+msg/s'
        r'.*?received:\s+([\d.]+)\s+msg/s'
        r'.*?min/median/75th/95th/99th/max consumer latency:\s*'
        r'([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*µs',
        re.DOTALL
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return {}

    m = matches[-1]
    us_to_ms = lambda x: round(float(x) / 1000, 3)
    return {
        "send_rate_rps": float(m.group(1)),
        "recv_rate_rps": float(m.group(2)),
        "min_ms":        us_to_ms(m.group(3)),
        "p50_ms":        us_to_ms(m.group(4)),
        "p75_ms":        us_to_ms(m.group(5)),
        "p95_ms":        us_to_ms(m.group(6)),
        "p99_ms":        us_to_ms(m.group(7)),
        "max_ms":        us_to_ms(m.group(8)),
    }


def parse_tcp(path):
    """
    Parse pillar1_tcp.py output.

    Format:
      Requests/sec   : 12345.67
      Avg latency    : 1.23 ms
      P50 latency    : 1.10 ms
      P75 latency    : 1.45 ms
      P90 latency    : 1.80 ms
      P99 latency    : 3.20 ms
    """
    if not os.path.exists(path):
        return {}
    text = open(path).read()

    def find(pattern, default=None):
        m = re.search(pattern, text)
        if not m:
            return default
        return float(m.group(1).replace(',', ''))

    rps = find(r'Requests/sec\s*:\s*([\d,]+\.?\d*)')
    avg = find(r'Avg latency\s*:\s*([\d.]+)\s*ms')
    p50 = find(r'P50 latency\s*:\s*([\d.]+)\s*ms')
    p75 = find(r'P75 latency\s*:\s*([\d.]+)\s*ms')
    p90 = find(r'P90 latency\s*:\s*([\d.]+)\s*ms')
    p99 = find(r'P99 latency\s*:\s*([\d.]+)\s*ms')

    if rps is None:
        return {}

    return {
        "rps": rps, "avg_ms": avg,
        "p50_ms": p50, "p75_ms": p75,
        "p90_ms": p90, "p99_ms": p99,
    }


def parse_wire(summary_path, rest_pcap, grpc_pcap, n=200):
    """
    Parse Pillar 2 wire data.

    Prefers the summary file saved by pillar2_wire.sh.
    Falls back to re-running tshark on the pcap files if summary is absent.
    """
    if os.path.exists(summary_path):
        text = open(summary_path).read()
        wire = {}
        for proto in ('REST', 'gRPC'):
            m_total = re.search(rf'{proto}\s+\S+\s+total wire bytes:\s+(\d+)', text)
            m_avg   = re.search(rf'{proto}\s+\S+.*?avg per request:\s+(\d+)', text)
            if m_total and m_avg:
                total = int(m_total.group(1))
                avg   = int(m_avg.group(1))
                wire[proto] = {
                    "total_wire_bytes":      total,
                    "num_requests":          n,
                    "avg_bytes_per_request": avg,
                    "overhead_bytes":        avg - 10240,
                }
        return wire

    # Fallback: tshark on pcap files
    import subprocess
    wire = {}
    for proto, pcap in [('REST', rest_pcap), ('gRPC', grpc_pcap)]:
        if not os.path.exists(pcap):
            print(f"  WARNING: {pcap} not found — skipping {proto} wire data")
            continue
        try:
            out = subprocess.check_output(
                ['tshark', '-r', pcap, '-T', 'fields', '-e', 'frame.len'],
                stderr=subprocess.DEVNULL
            ).decode()
            total = sum(int(x) for x in out.split() if x.isdigit())
            avg   = total // n
            wire[proto] = {
                "total_wire_bytes":      total,
                "num_requests":          n,
                "avg_bytes_per_request": avg,
                "overhead_bytes":        avg - 10240,
            }
        except Exception as e:
            print(f"  WARNING: tshark failed for {proto}: {e}")
    return wire


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=os.path.join(ROOT_DIR, 'results', 'results.json'))
    parser.add_argument('--wire-n', type=int, default=200,
                        help='Number of requests used in Pillar 2 capture (default 200)')
    args = parser.parse_args()

    rest_path     = os.path.join(SCRIPT_DIR, 'rest_10.txt')
    grpc_path     = os.path.join(SCRIPT_DIR, 'grpc_10.txt')
    kafka_path    = os.path.join(SCRIPT_DIR, 'kafka_out.txt')
    rabbitmq_path = os.path.join(SCRIPT_DIR, 'rabbitmq_out.txt')
    tcp_path      = os.path.join(SCRIPT_DIR, 'tcp_out.txt')
    p3_path       = os.path.join(SCRIPT_DIR, 'pillar3_out.txt')
    p2_summary    = os.path.join(SCRIPT_DIR, 'pillar2_out.txt')
    rest_strace   = '/tmp/p4_rest_strace.txt'
    grpc_strace   = '/tmp/p4_grpc_strace.txt'
    tcp_strace    = '/tmp/p4_tcp_strace.txt'
    rest_pcap     = '/tmp/p2_rest.pcap'
    grpc_pcap     = '/tmp/p2_grpc.pcap'

    results = {}

    # ── Pillar 1: REST ────────────────────────────────────────────────────
    if os.path.exists(rest_path) and os.path.getsize(rest_path) > 0:
        results['rest'] = parse_wrk(rest_path)
        print(f"REST     parsed: {results['rest']}")
    else:
        print(f"WARNING: {rest_path} missing — run pillar1_latency.sh first")

    # ── Pillar 1: gRPC ────────────────────────────────────────────────────
    if os.path.exists(grpc_path) and os.path.getsize(grpc_path) > 0:
        results['grpc'] = parse_ghz(grpc_path)
        print(f"gRPC     parsed: {results['grpc']}")
    else:
        print(f"WARNING: {grpc_path} missing — run pillar1_latency.sh first")

    # ── Pillar 1: Kafka ───────────────────────────────────────────────────
    if os.path.exists(kafka_path) and os.path.getsize(kafka_path) > 0:
        kafka = parse_kafka(kafka_path)
        if kafka:
            results['kafka'] = kafka
            print(f"Kafka    parsed: {kafka}")
        else:
            print(f"WARNING: {kafka_path} exists but could not be parsed")
    else:
        print(f"WARNING: {kafka_path} missing — run pillar1_brokers.sh first")

    # ── Pillar 1: RabbitMQ ────────────────────────────────────────────────
    if os.path.exists(rabbitmq_path) and os.path.getsize(rabbitmq_path) > 0:
        rmq = parse_rabbitmq(rabbitmq_path)
        if rmq:
            results['rabbitmq'] = rmq
            print(f"RabbitMQ parsed: {rmq}")
        else:
            print(f"WARNING: {rabbitmq_path} exists but could not be parsed")
    else:
        print(f"WARNING: {rabbitmq_path} missing — run pillar1_brokers.sh first")

    # ── Pillar 1: TCP ─────────────────────────────────────────────────────
    if os.path.exists(tcp_path) and os.path.getsize(tcp_path) > 0:
        tcp = parse_tcp(tcp_path)
        if tcp:
            results['tcp'] = tcp
            print(f"TCP      parsed: {tcp}")
        else:
            print(f"WARNING: {tcp_path} exists but could not be parsed")
    else:
        print(f"WARNING: {tcp_path} missing — run: python3 benchmarks/pillar1_tcp.py")

    # ── Pillar 2: Wire efficiency ─────────────────────────────────────────
    wire = parse_wire(p2_summary, rest_pcap, grpc_pcap, n=args.wire_n)
    if wire:
        results['wire'] = wire
        print(f"Wire     parsed: {wire}")
    else:
        print(f"WARNING: no Pillar 2 wire data — run pillar2_wire.sh first")

    # ── Pillar 3: Serialization CPU ───────────────────────────────────────
    p3 = parse_pillar3(p3_path)
    if p3:
        results['serialization'] = p3
        print(f"Pillar3  parsed: {p3}")
    else:
        print(f"WARNING: {p3_path} missing — run: python3 benchmarks/pillar3_cpu.py > benchmarks/pillar3_out.txt")

    # ── Pillar 4: Syscalls ────────────────────────────────────────────────
    syscalls = {}
    rest_sc = parse_strace(rest_strace)
    if rest_sc:
        syscalls['REST'] = rest_sc
        print(f"Strace REST parsed: total_calls={rest_sc.get('total_calls')}")
    else:
        print(f"WARNING: {rest_strace} missing — run pillar4_syscalls.sh first")

    grpc_sc = parse_strace(grpc_strace)
    if grpc_sc:
        syscalls['gRPC'] = grpc_sc
        print(f"Strace gRPC parsed: total_calls={grpc_sc.get('total_calls')}")
    else:
        print(f"WARNING: {grpc_strace} missing — run pillar4_syscalls.sh first")

    tcp_sc = parse_strace(tcp_strace)
    if tcp_sc:
        syscalls['TCP'] = tcp_sc
        print(f"Strace TCP  parsed: total_calls={tcp_sc.get('total_calls')}")
    else:
        print(f"WARNING: {tcp_strace} missing — run TCP strace capture first")

    if syscalls:
        results['syscalls'] = syscalls

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {args.out}")


if __name__ == '__main__':
    main()
