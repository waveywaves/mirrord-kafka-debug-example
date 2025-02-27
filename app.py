from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from confluent_kafka import Producer, Consumer, KafkaError
import json
import threading
import os
import logging
from dotenv import load_dotenv
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
# Configure SocketIO for production use with eventlet
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*', logger=True, engineio_logger=True)

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'test-topic')
APP_MODE = os.getenv('APP_MODE', 'producer')  # 'producer' or 'consumer'

logger.info(f"Starting application in {APP_MODE} mode")
logger.info(f"Kafka broker: {KAFKA_BOOTSTRAP_SERVERS}")
logger.info(f"Kafka topic: {KAFKA_TOPIC}")

producer = None
consumer_thread = None
consumer_running = threading.Event()

def delivery_report(err, msg):
    if err is not None:
        logger.error(f'Message delivery failed: {err}')
    else:
        logger.info(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')

if APP_MODE == 'producer':
    logger.info("Initializing Kafka producer...")
    # Initialize Kafka producer
    producer_config = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'client.id': 'python-producer'
    }
    producer = Producer(producer_config)
    logger.info("Kafka producer initialized successfully")
elif APP_MODE == 'consumer':
    logger.info("Initializing Kafka consumer...")
    # Consumer thread
    def kafka_consumer_thread():
        logger.info("Starting consumer thread...")
        try:
            consumer_config = {
                'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
                'group.id': 'test-consumer-group',
                'auto.offset.reset': 'latest',
                'enable.auto.commit': True
            }
            consumer = Consumer(consumer_config)
            consumer.subscribe([KAFKA_TOPIC])
            logger.info("Consumer connected successfully")
            
            consumer_running.set()
            while consumer_running.is_set():
                try:
                    msg = consumer.poll(1.0)
                    if msg is None:
                        continue
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            logger.debug('Reached end of partition')
                        else:
                            logger.error(f'Error while consuming: {msg.error()}')
                    else:
                        try:
                            value = json.loads(msg.value().decode('utf-8'))
                            logger.info(f"Received message: {value}")
                            socketio.emit('kafka_message', {
                                'value': value,
                                'timestamp': msg.timestamp()[1],
                                'partition': msg.partition(),
                                'offset': msg.offset(),
                                'topic': msg.topic()
                            })
                        except json.JSONDecodeError as e:
                            logger.error(f"Error decoding message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    time.sleep(1)  # Wait before retrying
        except Exception as e:
            logger.error(f"Consumer thread error: {str(e)}", exc_info=True)
            consumer_running.clear()
        finally:
            logger.info("Consumer thread stopping...")
            try:
                consumer.close()
            except Exception as e:
                logger.error(f"Error closing consumer: {str(e)}", exc_info=True)

    consumer_thread = threading.Thread(target=kafka_consumer_thread)
    consumer_thread.daemon = True
    consumer_thread.start()
    logger.info("Consumer thread started")

    # Wait for consumer to be ready
    if not consumer_running.wait(timeout=10):
        logger.error("Consumer failed to start within timeout")

@app.route('/')
def index():
    logger.info(f"Serving index page in {APP_MODE} mode")
    return render_template('index.html', mode=APP_MODE)

@app.route('/produce', methods=['POST'])
def produce_message():
    if APP_MODE != 'producer':
        logger.error(f"Produce endpoint called but running in {APP_MODE} mode")
        return jsonify({'error': 'This instance is not configured as a producer'}), 400

    data = request.json
    message = data.get('message')
    
    if not message:
        logger.warning("Empty message received")
        return jsonify({'error': 'No message provided'}), 400
    
    try:
        logger.info(f"Sending message: {message}")
        # Convert message to JSON string and encode as bytes
        message_bytes = json.dumps(message).encode('utf-8')
        producer.produce(KAFKA_TOPIC, value=message_bytes, callback=delivery_report)
        producer.flush(timeout=10)
        
        response = {
            'success': True,
            'message': 'Message sent successfully'
        }
        logger.info(f"Message sent successfully: {response}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    status_info = {
        'mode': APP_MODE,
        'kafka_broker': KAFKA_BOOTSTRAP_SERVERS,
        'topic': KAFKA_TOPIC,
        'status': 'running',
        'producer_initialized': producer is not None,
        'consumer_thread_running': consumer_thread is not None and consumer_thread.is_alive() and consumer_running.is_set()
    }
    logger.info(f"Status check: {status_info}")
    return jsonify(status_info)

if __name__ == '__main__':
    try:
        logger.info("Starting Flask-SocketIO server on http://0.0.0.0:5000")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        consumer_running.clear()
        if consumer_thread:
            consumer_thread.join(timeout=5)
    except Exception as e:
        logger.error(f"Error running app: {str(e)}", exc_info=True) 