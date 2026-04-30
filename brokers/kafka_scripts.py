import sys
import os
import json
from confluent_kafka import Producer, Consumer, KafkaError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from payload_gen.generator import PAYLOAD_1KB, PAYLOAD_10KB, PAYLOAD_100KB

KAFKA_BROKER = "localhost:9092"
TOPIC = "test_topic"

def get_producer():
    conf = {'bootstrap.servers': KAFKA_BROKER}
    return Producer(conf)

def produce_messages(producer, payload, count):
    # Simulate realistic serialization
    data = json.dumps(payload).encode('utf-8')
    for _ in range(count):
        producer.produce(TOPIC, data)
    producer.flush()

def get_consumer():
    conf = {
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': "benchmark_group",
        'auto.offset.reset': 'earliest'
    }
    consumer = Consumer(conf)
    consumer.subscribe([TOPIC])
    return consumer

def consume_messages(consumer, count):
    msgs_read = 0
    while msgs_read < count:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                break
                
        # Mimic decoding
        parsed = json.loads(msg.value().decode('utf-8'))
        msgs_read += 1
