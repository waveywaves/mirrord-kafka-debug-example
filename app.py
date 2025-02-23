from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from kafka import KafkaProducer, KafkaConsumer
import json
import threading
import os
import logging
from dotenv import load_dotenv

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

if APP_MODE == 'producer':
    logger.info("Initializing Kafka producer...")
    # Initialize Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    logger.info("Kafka producer initialized successfully")
elif APP_MODE == 'consumer':
    logger.info("Initializing Kafka consumer...")
    # Consumer thread
    def kafka_consumer_thread():
        logger.info("Starting consumer thread...")
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='test-consumer-group'
        )
        logger.info("Consumer connected successfully")
        
        for message in consumer:
            logger.debug(f"Received message: {message.value}")
            socketio.emit('kafka_message', {
                'value': message.value,
                'timestamp': message.timestamp,
                'partition': message.partition,
                'offset': message.offset,
                'topic': message.topic
            })

    consumer_thread = threading.Thread(target=kafka_consumer_thread)
    consumer_thread.daemon = True
    consumer_thread.start()
    logger.info("Consumer thread started")

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
        future = producer.send(KAFKA_TOPIC, value=message)
        record_metadata = future.get(timeout=10)
        producer.flush()
        
        response = {
            'success': True,
            'message': 'Message sent successfully',
            'metadata': {
                'topic': record_metadata.topic,
                'partition': record_metadata.partition,
                'offset': record_metadata.offset
            }
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
        'consumer_thread_running': consumer_thread is not None and consumer_thread.is_alive() if consumer_thread else False
    }
    logger.info(f"Status check: {status_info}")
    return jsonify(status_info)

# Remove the direct run call as we're using Gunicorn
# The socketio instance is used by Gunicorn 