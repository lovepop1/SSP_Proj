import uuid
import time
import random

def generate_transaction(target_size_bytes: int) -> dict:
    """
    Generates a transaction dictionary approximating the target byte size.
    The size difference is padded into the 'metadata' field.
    """
    txn = {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "user_id": random.randint(1000, 9999),
        "amount": round(random.uniform(10.0, 1000.0), 2),
        "currency": "USD",
        "description": "Standard service payment",
        "merchant_code": f"M{random.randint(100, 999)}",
        "metadata": ""
    }
    
    # We estimate the base overhead of the fields when represented as strings
    # Real sizes vary slightly depending on serialization format (JSON config vs protobuf binary)
    # We add exact characters to ensure the raw semantic data has the desired bulk.
    overhead = 220 
    padding = max(0, target_size_bytes - overhead)
    txn["metadata"] = "X" * padding
    
    return txn

# Pre-generate singletons for benchmarks to avoid generation overhead during the test itself
PAYLOAD_1KB = generate_transaction(1024)
PAYLOAD_10KB = generate_transaction(10 * 1024)
PAYLOAD_100KB = generate_transaction(100 * 1024)

if __name__ == "__main__":
    import json
    for size, p in [("1KB", PAYLOAD_1KB), ("10KB", PAYLOAD_10KB), ("100KB", PAYLOAD_100KB)]:
        encoded = json.dumps(p)
        print(f"JSON Length of {size} payload: {len(encoded)} bytes")
