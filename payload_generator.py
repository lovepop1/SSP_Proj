import json
import time
from datetime import datetime

# The base size of the other fields is roughly 150 bytes
BASE_SIZE = 150

def generate_10kb_payload():
    """Generate exactly 10KB transaction payload for both REST and gRPC"""
    target_size_kb = 10
    target_bytes = target_size_kb * 1024
    padding_length = target_bytes - BASE_SIZE
    
    # Python makes this easy: multiplying a character creates a string of that length
    padding_string = "x" * padding_length
    
    # REST/JSON payload
    json_payload = {
        "transaction_id": 1048573,
        "timestamp": "2026-03-16T15:30:00.000Z",
        "user_id": "usr_948172635",
        "event_type": "PURCHASE",
        "amount": 299.99,
        "padding": padding_string
    }
    
    return json_payload

def get_payload_size_info():
    """Get information about the payload size for verification"""
    payload = generate_10kb_payload()
    json_string = json.dumps(payload)
    return {
        "target_bytes": 10 * 1024,
        "actual_json_bytes": len(json_string.encode('utf-8')),
        "padding_length": len(payload["padding"])
    }

if __name__ == "__main__":
    # Test the payload generation
    size_info = get_payload_size_info()
    print("10KB Payload Size Verification:")
    print(f"Target: {size_info['target_bytes']} bytes")
    print(f"Actual JSON: {size_info['actual_json_bytes']} bytes")
    print(f"Padding length: {size_info['padding_length']} characters")
