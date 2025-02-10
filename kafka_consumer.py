from kafka import KafkaConsumer
import json
import os
from kafka.errors import NoBrokersAvailable
import time
import sys

def create_consumer(topic):
    # Create a Kafka consumer instance
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    group_id = os.getenv('KAFKA_GROUP_ID', 'test-consumer-group')
    retries = 30
    while retries > 0:
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=[bootstrap_servers],
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id=group_id,
                reconnect_backoff_ms=1000,
                reconnect_backoff_max_ms=5000,
                retry_backoff_ms=1000
            )
            print(f"Successfully connected to Kafka at {bootstrap_servers}")
            return consumer
        except NoBrokersAvailable:
            print(f"Waiting for Kafka to be available at {bootstrap_servers}... {retries} retries left")
            retries -= 1
            time.sleep(2)
    
    print("Failed to connect to Kafka after all retries")
    sys.exit(1)

def main():
    topic = os.getenv('KAFKA_TOPIC_NAME', 'test_topic')
    consumer = create_consumer(topic)
    
    print(f"Starting to consume messages from topic {topic}...")
    try:
        for message in consumer:
            print("\nReceived message:")
            print(f"Topic: {message.topic}")
            print(f"Partition: {message.partition}")
            print(f"Offset: {message.offset}")
            print(f"Key: {message.key}")
            print(f"Value: {message.value}")
    except KeyboardInterrupt:
        print("Stopping consumer...")
    finally:
        consumer.close()

if __name__ == '__main__':
    main() 