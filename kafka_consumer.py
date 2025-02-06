from kafka import KafkaConsumer
import json
import os

def create_consumer(topic):
    # Create a Kafka consumer instance
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=[bootstrap_servers],
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='my_consumer_group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    return consumer

def main():
    topic = 'test_topic'
    consumer = create_consumer(topic)
    
    print(f"Starting to consume messages from topic: {topic}")
    try:
        for message in consumer:
            print("\nReceived message:")
            print(f"Topic: {message.topic}")
            print(f"Partition: {message.partition}")
            print(f"Offset: {message.offset}")
            print(f"Key: {message.key}")
            print(f"Value: {message.value}")
    except KeyboardInterrupt:
        print("\nStopping the consumer...")
    finally:
        consumer.close()

if __name__ == '__main__':
    main() 