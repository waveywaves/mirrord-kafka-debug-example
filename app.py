from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from confluent_kafka import Producer, Consumer, KafkaError
import json
import threading
import os
import logging
from dotenv import load_dotenv
import time
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
# Configure SocketIO for production use with eventlet
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*', logger=True, engineio_logger=True, ping_timeout=60, ping_interval=25)

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
last_consumer_activity = time.time()  # Track when the consumer was last active

# In-memory storage for tracking messages and their delivery reports
pending_messages = {}
# Track the last message ID for delivery reports
last_message_id = None

def delivery_report(err, msg):
    global pending_messages, last_message_id
    
    if err is not None:
        logger.error(f'Message delivery failed: {err}')
        # If we have the message ID, update its status
        for msg_id, msg_data in list(pending_messages.items()):
            if msg_data.get('timestamp') < time.time() - 30:  # Clean up old pending messages
                pending_messages.pop(msg_id, None)
    else:
        logger.info(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')
        
        # Use the last_message_id to update the metadata
        if last_message_id and last_message_id in pending_messages:
            msg_id = last_message_id
            pending_messages[msg_id]['metadata'] = {
                'partition': msg.partition(),
                'offset': msg.offset(),
                'topic': msg.topic()
            }
            # Emit the updated metadata to the client via WebSocket
            socketio.emit('message_metadata_update', {
                'message_id': msg_id,
                'metadata': pending_messages[msg_id]['metadata']
            })
            logger.info(f"Updated metadata for message {msg_id}: {pending_messages[msg_id]['metadata']}")

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
                'enable.auto.commit': True,
                'session.timeout.ms': 10000,  # Increased timeout
                'max.poll.interval.ms': 300000  # Allow more time between polls
            }
            consumer = Consumer(consumer_config)
            consumer.subscribe([KAFKA_TOPIC])
            logger.info("Consumer connected successfully")
            
            global last_consumer_activity
            consumer_running.set()
            last_consumer_activity = time.time()
            
            while consumer_running.is_set():
                try:
                    # Use a shorter timeout for poll to keep the thread responsive
                    msg = consumer.poll(0.5)
                    last_consumer_activity = time.time()  # Update activity timestamp
                    
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
                            
                            # Send the message to connected clients via WebSocket
                            message_data = {
                                'value': value,
                                'timestamp': msg.timestamp()[1],
                                'partition': msg.partition(),
                                'offset': msg.offset(),
                                'topic': msg.topic()
                            }
                            logger.info(f"Emitting message via Socket.IO: {message_data}")
                            socketio.emit('kafka_message', message_data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Error decoding message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    time.sleep(0.5)  # Reduced wait time for retries
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
    global last_message_id
    
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
        
        # Generate a unique ID for this message to track it
        message_id = str(uuid.uuid4())
        last_message_id = message_id  # Store for delivery report
        
        # Store initial data in our tracking dictionary
        pending_messages[message_id] = {
            'message': message,
            'timestamp': time.time(),
            'metadata': {
                'partition': 'pending',  # Will be filled by delivery report
                'offset': 'pending',     # Will be filled by delivery report
                'topic': KAFKA_TOPIC
            }
        }
        
        # Convert message to JSON string and encode as bytes
        message_bytes = json.dumps(message).encode('utf-8')
        
        # Produce the message with a 'source' header for mirrord filtering
        producer.produce(
            KAFKA_TOPIC, 
            value=message_bytes, 
            callback=delivery_report,
            headers=[('source', f'test-{message_id}'.encode('utf-8'))]
        )
        producer.flush(timeout=1)  # Short flush - delivery report will come later
        
        response = {
            'success': True,
            'message': 'Message sent successfully',
            'message_id': message_id,
            'metadata': pending_messages[message_id]['metadata']
        }
        logger.info(f"Message queued for delivery: {response}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    # Calculate consumer health based on recent activity
    consumer_health = 'healthy'
    if APP_MODE == 'consumer' and consumer_thread is not None:
        if not consumer_running.is_set():
            consumer_health = 'stopped'
        elif time.time() - last_consumer_activity > 30:  # If no activity for 30 seconds
            consumer_health = 'stalled'
    
    status_info = {
        'mode': APP_MODE,
        'kafka_broker': KAFKA_BOOTSTRAP_SERVERS,
        'topic': KAFKA_TOPIC,
        'status': 'running',
        'consumer_health': consumer_health,
        'producer_initialized': producer is not None,
        'consumer_thread_running': consumer_thread is not None and consumer_thread.is_alive() and consumer_running.is_set(),
        'timestamp': int(time.time())
    }
    logger.info(f"Status check: {status_info}")
    return jsonify(status_info)

# WebSocket events
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected - Mode: {APP_MODE}")
    
@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

if __name__ == '__main__':
    try:
        logger.info(f"Starting Flask-SocketIO server on http://0.0.0.0:9090")
        # Use longer timeout and disable ping interval
        socketio.run(app, host='0.0.0.0', port=9090, debug=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        consumer_running.clear()
        if consumer_thread:
            consumer_thread.join(timeout=5)
    except Exception as e:
        logger.error(f"Error running app: {str(e)}", exc_info=True) 