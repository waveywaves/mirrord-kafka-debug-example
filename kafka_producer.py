from kafka import KafkaProducer
import json
import time
import os
import random
from kafka.errors import NoBrokersAvailable
import sys

def create_producer():
    # Create a Kafka producer instance
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    retries = 30
    while retries > 0:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                reconnect_backoff_ms=1000,
                reconnect_backoff_max_ms=5000,
                retry_backoff_ms=1000
            )
            print(f"Successfully connected to Kafka at {bootstrap_servers}")
            return producer
        except NoBrokersAvailable:
            print(f"Waiting for Kafka to be available at {bootstrap_servers}... {retries} retries left")
            retries -= 1
            time.sleep(2)
    
    print("Failed to connect to Kafka after all retries")
    sys.exit(1)

def send_message(producer, topic, message):
    # Send message to specified topic
    future = producer.send(topic, message)
    try:
        # Wait for message to be delivered
        record_metadata = future.get(timeout=10)
        print(f"Message sent successfully to topic {record_metadata.topic}")
        print(f"Partition: {record_metadata.partition}")
        print(f"Offset: {record_metadata.offset}")
        print(f"Value: {message}")
    except Exception as e:
        print(f"Error sending message: {e}")

def main():
    producer = create_producer()
    topic = 'test_topic'
    
    print("Starting to send random numbers...")
    try:
        while True:
            # Generate a random number between 1 and 1000
            random_number = random.randint(1, 1000)
            message = {
                'timestamp': time.time(),
                'value': random_number
            }
            send_message(producer, topic, message)
            time.sleep(1)  # Wait 1 second between messages
    except KeyboardInterrupt:
        print("Stopping producer...")
    finally:
        producer.close()

if __name__ == '__main__':
    main() 