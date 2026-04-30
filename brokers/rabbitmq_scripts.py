import pika
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from payload_gen.generator import PAYLOAD_1KB, PAYLOAD_10KB, PAYLOAD_100KB

QUEUE = "test_queue"

def get_connection():
    params = pika.ConnectionParameters(host='localhost', port=5672)
    return pika.BlockingConnection(params)

def setup_queue(channel):
    channel.queue_declare(queue=QUEUE, durable=False)

def produce_messages(payload, count):
    conn = get_connection()
    channel = conn.channel()
    setup_queue(channel)
    data = json.dumps(payload).encode('utf-8')
    
    for _ in range(count):
        channel.basic_publish(exchange='', routing_key=QUEUE, body=data)
    conn.close()

def consume_messages(count):
    conn = get_connection()
    channel = conn.channel()
    setup_queue(channel)
    
    msgs_read = 0
    def callback(ch, method, properties, body):
        nonlocal msgs_read
        parsed = json.loads(body.decode('utf-8'))
        msgs_read += 1
        if msgs_read >= count:
            ch.stop_consuming()
            
    channel.basic_consume(queue=QUEUE, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()
    conn.close()
