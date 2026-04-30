"""
Pillar 3: CPU Serialization Overhead
- JSON: json.dumps().encode() per iteration (full serialization cost)
- Protobuf: object construction + SerializeToString() per iteration
  (construction is included because it is unavoidable in real request handling)
- Reports time as microseconds/op and as % of total combined time
- Saves cProfile trace to benchmarks/pillar3_profile.prof
"""
import sys, os, time, json, cProfile, pstats

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'payload_gen'))
from generator import PAYLOAD_10KB
import schema_pb2

ITERATIONS = 10_000

def bench_json(n):
    t0 = time.perf_counter()
    for _ in range(n):
        _ = json.dumps(PAYLOAD_10KB).encode('utf-8')
    return time.perf_counter() - t0

def bench_proto(n):
    # Include object construction — this is the real cost in a request handler
    t0 = time.perf_counter()
    for _ in range(n):
        msg = schema_pb2.Transaction(**PAYLOAD_10KB)
        _ = msg.SerializeToString()
    return time.perf_counter() - t0

def run():
    print(f"Pillar 3: CPU Serialization Overhead ({ITERATIONS:,} iterations, 10KB payload)")
    print("=" * 60)

    # Warmup (avoids JIT/import noise in first few iterations)
    bench_json(100)
    bench_proto(100)

    profiler = cProfile.Profile()
    profiler.enable()
    json_time = bench_json(ITERATIONS)
    proto_time = bench_proto(ITERATIONS)
    profiler.disable()

    total = json_time + proto_time
    json_us  = (json_time  / ITERATIONS) * 1e6
    proto_us = (proto_time / ITERATIONS) * 1e6

    print(f"\nJSON  total: {json_time:.4f}s  |  avg: {json_us:.2f} µs/op  |  share: {json_time/total*100:.1f}%")
    print(f"Proto total: {proto_time:.4f}s  |  avg: {proto_us:.2f} µs/op  |  share: {proto_time/total*100:.1f}%")
    print(f"\nSpeedup: Protobuf is {json_us/proto_us:.2f}x faster than JSON per operation")

    # Payload sizes
    json_size  = len(json.dumps(PAYLOAD_10KB).encode('utf-8'))
    proto_size = len(schema_pb2.Transaction(**PAYLOAD_10KB).SerializeToString())
    print(f"\nJSON  serialized size: {json_size} bytes")
    print(f"Proto serialized size: {proto_size} bytes")
    print(f"Proto is {json_size - proto_size} bytes smaller ({(1 - proto_size/json_size)*100:.1f}% reduction)")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pillar3_profile.prof')
    stats = pstats.Stats(profiler)
    stats.dump_stats(out)
    print(f"\ncProfile trace saved to {out}")

if __name__ == '__main__':
    run()
