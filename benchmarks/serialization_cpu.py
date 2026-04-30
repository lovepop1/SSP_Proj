#!/usr/bin/env python3
"""
Serialization CPU Cost Benchmark
Tests: 10,000 requests to measure JSON vs Protobuf serialization overhead
"""

import cProfile
import pstats
import io
import json
import time
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payload_generator import generate_10kb_payload
import transaction_pb2

def benchmark_json_serialization(iterations=10000):
    """Benchmark JSON serialization for 10,000 iterations"""
    payload = generate_10kb_payload()
    
    json_times = []
    total_start = time.perf_counter()
    
    for i in range(iterations):
        start = time.perf_counter()
        json_str = json.dumps(payload)
        end = time.perf_counter()
        json_times.append(end - start)
    
    total_end = time.perf_counter()
    
    return {
        'total_time': total_end - total_start,
        'avg_time_per_serialization': sum(json_times) / len(json_times),
        'max_time': max(json_times),
        'min_time': min(json_times),
        'iterations': iterations,
        'avg_payload_size': len(json_str.encode('utf-8'))
    }

def benchmark_protobuf_serialization(iterations=10000):
    """Benchmark Protobuf serialization for 10,000 iterations"""
    payload = generate_10kb_payload()
    
    protobuf_times = []
    total_start = time.perf_counter()
    
    for i in range(iterations):
        start = time.perf_counter()
        # Create protobuf message
        proto_msg = transaction_pb2.Transaction(
            transaction_id=payload['transaction_id'],
            timestamp=payload['timestamp'],
            user_id=payload['user_id'],
            event_type=payload['event_type'],
            amount=payload['amount'],
            padding=payload['padding']
        )
        # Serialize to string
        proto_bytes = proto_msg.SerializeToString()
        end = time.perf_counter()
        protobuf_times.append(end - start)
    
    total_end = time.perf_counter()
    
    return {
        'total_time': total_end - total_start,
        'avg_time_per_serialization': sum(protobuf_times) / len(protobuf_times),
        'max_time': max(protobuf_times),
        'min_time': min(protobuf_times),
        'iterations': iterations,
        'avg_payload_size': len(proto_bytes)
    }

def profile_json_serialization():
    """Profile JSON serialization to see where time is spent"""
    print("🔍 Profiling JSON serialization...")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    payload = generate_10kb_payload()
    for i in range(10000):
        json_str = json.dumps(payload)
    
    profiler.disable()
    
    # Create stats object
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions
    
    return s.getvalue()

def profile_protobuf_serialization():
    """Profile Protobuf serialization to see where time is spent"""
    print("🔍 Profiling Protobuf serialization...")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    payload = generate_10kb_payload()
    for i in range(10000):
        proto_msg = transaction_pb2.Transaction(
            transaction_id=payload['transaction_id'],
            timestamp=payload['timestamp'],
            user_id=payload['user_id'],
            event_type=payload['event_type'],
            amount=payload['amount'],
            padding=payload['padding']
        )
        proto_bytes = proto_msg.SerializeToString()
    
    profiler.disable()
    
    # Create stats object
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions
    
    return s.getvalue()

def main():
    print("🧠 Serialization CPU Cost Benchmark")
    print("====================================")
    print("Testing 10,000 iterations with 10KB payload")
    print()
    
    # Benchmark JSON
    print("📊 Testing JSON serialization...")
    json_results = benchmark_json_serialization()
    
    print(f"   Total time: {json_results['total_time']:.4f}s")
    print(f"   Avg per serialization: {json_results['avg_time_per_serialization']*1000:.4f}ms")
    print(f"   Max time: {json_results['max_time']*1000:.4f}ms")
    print(f"   Min time: {json_results['min_time']*1000:.4f}ms")
    print(f"   Avg payload size: {json_results['avg_payload_size']} bytes")
    print()
    
    # Benchmark Protobuf
    print("📊 Testing Protobuf serialization...")
    protobuf_results = benchmark_protobuf_serialization()
    
    print(f"   Total time: {protobuf_results['total_time']:.4f}s")
    print(f"   Avg per serialization: {protobuf_results['avg_time_per_serialization']*1000:.4f}ms")
    print(f"   Max time: {protobuf_results['max_time']*1000:.4f}ms")
    print(f"   Min time: {protobuf_results['min_time']*1000:.4f}ms")
    print(f"   Avg payload size: {protobuf_results['avg_payload_size']} bytes")
    print()
    
    # Calculate comparison
    print("📈 Comparison Results:")
    json_time_per_req = json_results['avg_time_per_serialization'] * 1000
    protobuf_time_per_req = protobuf_results['avg_time_per_serialization'] * 1000
    
    speedup = json_time_per_req / protobuf_time_per_req
    json_percentage = (json_results['total_time'] / (json_results['total_time'] + protobuf_results['total_time'])) * 100
    protobuf_percentage = (protobuf_results['total_time'] / (json_results['total_time'] + protobuf_results['total_time'])) * 100
    
    print(f"   JSON avg time per serialization: {json_time_per_req:.4f}ms")
    print(f"   Protobuf avg time per serialization: {protobuf_time_per_req:.4f}ms")
    print(f"   Protobuf is {speedup:.2f}x faster than JSON")
    print(f"   JSON spends {json_percentage:.1f}% of total serialization time")
    print(f"   Protobuf spends {protobuf_percentage:.1f}% of total serialization time")
    print()
    
    # Profile for detailed analysis
    print("🔍 Running detailed profiling (this may take a moment)...")
    print()
    
    json_profile = profile_json_serialization()
    print("📊 JSON Serialization Profile:")
    print(json_profile)
    print()
    
    protobuf_profile = profile_protobuf_serialization()
    print("📊 Protobuf Serialization Profile:")
    print(protobuf_profile)
    print()
    
    print("✅ Serialization CPU Cost Benchmark Complete!")
    print()
    print("🎯 Friday Deliverable Key Metrics:")
    print(f"   - REST spends {json_percentage:.1f}% of its total time building JSON strings")
    print(f"   - gRPC spends {protobuf_percentage:.1f}% of its total time in Protobuf serialization")
    print(f"   - Performance improvement: {speedup:.2f}x faster for Protobuf")

if __name__ == "__main__":
    main()
