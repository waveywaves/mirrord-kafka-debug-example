FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY kafka_producer.py .
COPY kafka_consumer.py . 