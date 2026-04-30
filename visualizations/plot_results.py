"""
plot_results.py — generates all benchmark figures for report.latex from results/results.json.

Output files (saved to visualizations/plots/):
  fig1_rps_comparison.png       — Pillar 1: Throughput (RPS)
  fig2_tail_latency.png         — Pillar 1: P50 / P99 latency
  fig3_wire_bloat.png           — Pillar 2: Wire-level byte overhead
  fig4_serialization.png        — Pillar 3: Serialization CPU cost
  fig5_syscall_overhead.png     — Pillar 4: Kernel syscall count

Usage (run from project root):
  python3 visualizations/plot_results.py
  python3 visualizations/plot_results.py --data results/results.json --out visualizations/plots
"""

import json, os, sys, argparse
import matplotlib
matplotlib.use('Agg')   # headless — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)

# ── Shared style ──────────────────────────────────────────────────────────────
COLORS = {
    'TCP':      '#2196F3',   # blue
    'REST':     '#4CAF50',   # green
    'gRPC':     '#FF9800',   # orange
    'Kafka':    '#9C27B0',   # purple
    'RabbitMQ': '#E53935',   # red
    'JSON':     '#E53935',
    'Protobuf': '#1E88E5',
}

plt.rcParams.update({
    'font.family':      'serif',
    'font.size':        10,
    'axes.titlesize':   11,
    'axes.titleweight': 'bold',
    'axes.labelsize':   10,
    'axes.spines.top':  False,
    'axes.spines.right':False,
    'axes.grid':        True,
    'grid.alpha':       0.35,
    'figure.dpi':       150,
})


def load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def savefig(fig, path: str):
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved → {path}")


# ── Fig 1: RPS Comparison (Pillar 1) ─────────────────────────────────────────
def fig1_rps(data: dict, out_dir: str):
    entries = [
        ('RabbitMQ', data.get('rabbitmq', {}).get('send_rate_rps')),
        ('REST',     data.get('rest',     {}).get('rps')),
        ('TCP',      data.get('tcp',      {}).get('rps')),
        ('Kafka',    data.get('kafka',    {}).get('rps')),
        ('gRPC',     data.get('grpc',     {}).get('rps')),
    ]
    entries = [(lbl, v) for lbl, v in entries if v is not None]
    if not entries:
        print("  SKIP fig1 — no RPS data"); return

    labels, vals = zip(*entries)
    colors = [COLORS[l] for l in labels]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, vals, color=colors, width=0.55, edgecolor='white', linewidth=0.8)

    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(vals) * 0.012,
                f'{val:,.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_title('Pillar 1 — Throughput Comparison (10 KB payload, 50 concurrent connections)')
    ax.set_ylabel('Requests / second  (higher is better)')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.set_ylim(0, max(vals) * 1.22)

    # Annotation for brokers
    ax.annotate('Brokers: asynchronous\nshock-absorber role\n(not direct speed competitors)',
                xy=(0, vals[0]), xytext=(0.05, 0.80),
                textcoords='axes fraction',
                fontsize=7.5, color='#555',
                arrowprops=dict(arrowstyle='->', color='#888', lw=0.8))

    savefig(fig, os.path.join(out_dir, 'fig1_rps_comparison.png'))


# ── Fig 2: Tail Latency P50 / P99 (Pillar 1) ─────────────────────────────────
def fig2_latency(data: dict, out_dir: str):
    # Synchronous protocols — exclude Kafka (1200ms would crush the y-axis)
    proto_data = [
        ('REST',  data.get('rest',     {})),
        ('TCP',   data.get('tcp',      {})),
        ('gRPC',  data.get('grpc',     {})),
    ]
    labels = [lbl for lbl, _ in proto_data if _.get('p50_ms') is not None]
    p50    = [d.get('p50_ms') for _, d in proto_data if d.get('p50_ms') is not None]
    p99    = [d.get('p99_ms') for _, d in proto_data if d.get('p99_ms') is not None]

    if not labels:
        print("  SKIP fig2 — no latency data"); return

    x     = np.arange(len(labels))
    width = 0.32
    colors_50  = [COLORS[l] for l in labels]
    colors_99  = [COLORS[l] for l in labels]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    b1 = ax.bar(x - width/2, p50, width, label='P50 (median)', color=colors_50, alpha=0.9, edgecolor='white')
    b2 = ax.bar(x + width/2, p99, width, label='P99 (tail)',   color=colors_99, alpha=0.55, edgecolor='white', hatch='//')

    for bar, val in zip(list(b1) + list(b2), p50 + p99):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.25,
                f'{val:.1f}', ha='center', va='bottom', fontsize=8)

    ax.set_title('Pillar 1 — P50 / P99 Tail Latency, Synchronous Protocols (10 KB payload)\n'
                 'Note: Kafka P50 = 1,209 ms (disk durability guarantee) — off-scale, excluded for readability')
    ax.set_ylabel('Latency (ms)  ·  lower is better')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    savefig(fig, os.path.join(out_dir, 'fig2_tail_latency.png'))


# ── Fig 3: Wire Bloat (Pillar 2) ─────────────────────────────────────────────
def fig3_wire(data: dict, out_dir: str):
    wire = data.get('wire')
    if not wire:
        print("  SKIP fig3 — no wire data"); return

    # Add TCP approximation (payload size × 200, no framing)
    payload_bytes = data.get('serialization', {}).get('json_size_bytes', 10248)
    tcp_avg = round(payload_bytes)   # ~0 overhead

    proto_order = ['TCP', 'gRPC', 'REST']
    avgs = {
        'TCP':  tcp_avg,
        'gRPC': wire.get('gRPC', {}).get('avg_bytes_per_request'),
        'REST': wire.get('REST', {}).get('avg_bytes_per_request'),
    }
    avgs = {k: v for k, v in avgs.items() if v is not None}
    proto_order = [p for p in proto_order if p in avgs]

    labels = proto_order
    vals   = [avgs[p] for p in proto_order]
    colors = [COLORS[p] for p in proto_order]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, vals, color=colors, width=0.45, edgecolor='white')

    baseline = payload_bytes
    ax.axhline(baseline, color='#333', linestyle='--', linewidth=1.2,
               label=f'Semantic payload ({baseline:,.0f} B)')

    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(vals) * 0.013,
                f'{val:,} B', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Overhead annotations
    for i, (proto, val) in enumerate(zip(labels, vals)):
        overhead_pct = (val - baseline) / baseline * 100
        ax.text(i, val / 2,
                f'+{overhead_pct:.0f}%\noverhead' if overhead_pct > 0 else 'baseline',
                ha='center', va='center', fontsize=8, color='white', fontweight='bold')

    ax.set_title('Pillar 2 — Wire-Level Bytes per Request (200 requests, 10 KB semantic payload)\n'
                 'Kafka & RabbitMQ excluded: async batching frames are not comparable')
    ax.set_ylabel('Bytes per request  ·  lower is better')
    ax.legend()
    savefig(fig, os.path.join(out_dir, 'fig3_wire_bloat.png'))


# ── Fig 4: Serialization CPU cost (Pillar 3) ──────────────────────────────────
def fig4_serialization(data: dict, out_dir: str):
    s = data.get('serialization')
    if not s:
        print("  SKIP fig4 — no serialization data"); return

    json_us  = s.get('json_us_op')
    proto_us = s.get('proto_us_op')
    speedup  = s.get('speedup')

    if json_us is None or proto_us is None:
        print("  SKIP fig4 — incomplete serialization data"); return

    labels = ['JSON\n(REST)', 'Protobuf\n(gRPC)']
    vals   = [json_us, proto_us]
    colors = [COLORS['JSON'], COLORS['Protobuf']]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    bars = ax.bar(labels, vals, color=colors, width=0.38, edgecolor='white')

    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(vals) * 0.012,
                f'{val:.2f} µs', ha='center', va='bottom', fontsize=10, fontweight='bold')

    title = 'Pillar 3 — User-Space Serialization Cost per Operation\n(10,000 iterations, 10 KB payload)'
    if speedup:
        title += f'\nProtobuf is {speedup:.1f}× faster than JSON'
    ax.set_title(title)
    ax.set_ylabel('Microseconds per operation  ·  lower is better')

    # Speedup bracket
    ax.annotate('', xy=(1, proto_us), xytext=(0, json_us),
                arrowprops=dict(arrowstyle='<->', color='#333', lw=1.2))
    if speedup:
        ax.text(0.5, (json_us + proto_us) / 2,
                f'  {speedup:.1f}×', va='center', fontsize=9, color='#333')

    savefig(fig, os.path.join(out_dir, 'fig4_serialization.png'))


# ── Fig 5: Syscall Overhead (Pillar 4) ───────────────────────────────────────
def fig5_syscalls(data: dict, out_dir: str):
    sc = data.get('syscalls')
    if not sc:
        print("  SKIP fig5 — no syscall data"); return

    tcp_calls  = sc.get('TCP',  {}).get('total_calls')
    rest_calls = sc.get('REST', {}).get('total_calls')
    grpc_calls = sc.get('gRPC', {}).get('total_calls')

    entries = [('TCP', tcp_calls), ('REST', rest_calls), ('gRPC', grpc_calls)]
    entries = [(lbl, v) for lbl, v in entries if v is not None]
    if not entries:
        print("  SKIP fig5 — no useful syscall data"); return

    labels, vals = zip(*entries)
    colors = [COLORS[l] for l in labels]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, vals, color=colors, width=0.45, edgecolor='white')

    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(vals) * 0.012,
                f'{val:,}', ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Multiplier annotations relative to TCP baseline
    if tcp_calls:
        for i, (lbl, val) in enumerate(zip(labels, vals)):
            if lbl != 'TCP' and val:
                mult = val / tcp_calls
                ax.text(i, val * 0.5,
                        f'{mult:.1f}×\nbaseline',
                        ha='center', va='center', fontsize=8.5, color='white', fontweight='bold')

    ax.set_title('Pillar 4 — Kernel System Call Count (strace -c, 1,000 requests, 10 KB payload)\n'
                 'Brokers excluded: Docker container namespaces prevent clean strace coupling')
    ax.set_ylabel('Total syscalls  ·  lower is better')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    savefig(fig, os.path.join(out_dir, 'fig5_syscall_overhead.png'))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default=os.path.join(ROOT_DIR, 'results', 'results.json'))
    parser.add_argument('--out',  default=os.path.join(SCRIPT_DIR, 'plots'))
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"ERROR: {args.data} not found.")
        sys.exit(1)

    data = load(args.data)
    os.makedirs(args.out, exist_ok=True)

    print(f"Generating figures from {args.data} → {args.out}/")
    fig1_rps(data, args.out)
    fig2_latency(data, args.out)
    fig3_wire(data, args.out)
    fig4_serialization(data, args.out)
    fig5_syscalls(data, args.out)
    print("Done. Upload the 5 PNG files alongside report.latex to Overleaf.")


if __name__ == '__main__':
    main()
