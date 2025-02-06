from kafka import KafkaProducer
import json
import time
import os

def create_producer():
    # Create a Kafka producer instance
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    producer = KafkaProducer(
        bootstrap_servers=[bootstrap_servers],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    return producer

def send_message(producer, topic, message):
    # Send message to specified topic
    future = producer.send(topic, message)
    try:
        # Wait for message to be delivered
        record_metadata = future.get(timeout=10)
        print(f"Message sent successfully to topic {record_metadata.topic}")
        print(f"Partition: {record_metadata.partition}")
        print(f"Offset: {record_metadata.offset}")
    except Exception as e:
        print(f"Error sending message: {e}")

def main():
    producer = create_producer()
    topic = 'test_topic'
    
    # Send a few test messages
    for i in range(5):
        message = {
            'message_id': i,
            'content': f'Test message {i}',
            'timestamp': time.time()
        }
        send_message(producer, topic, message)
        time.sleep(1)  # Wait 1 second between messages
    
    producer.close()

if __name__ == '__main__':
    main() 