# Debugging Kafka Consumers with mirrord

<div align="center">
  <a href="https://mirrord.dev">
    <img src="images/mirrord.svg" width="150" alt="mirrord Logo"/>
  </a>
  <a href="https://kafka.apache.org">
    <img src="images/kafka.png" width="150" alt="Kafka Logo"/>
  </a>
</div>

A sample application demonstrating how to debug Kafka consumers using mirrord. This application features a producer service that publishes messages to a Kafka topic and a consumer service that reads and processes these messages.

## Tech Stack

- Python 3.9
- Flask
- Apache Kafka
- confluent-kafka Python library
- Kubernetes

## Features

- Producer service with a web UI for publishing messages
- Consumer service with a web UI that processes Kafka messages
- Kubernetes-ready deployment
- mirrord configuration for debugging Kafka consumers with two different approaches

## Prerequisites

- Python 3.9 or higher
- Kubernetes cluster
- kubectl
- mirrord CLI
- helm (for alternative mirrord operator installation)

## Setup Options

### 1. Local Development with Docker Compose

For testing locally without Kubernetes:

```bash
docker compose up --build
```

This will start the Kafka broker, producer, and consumer services in Docker containers.

### 2. Local Python Environment

If you prefer running the Python application directly:

```bash
conda create -n kafka-debug python=3.9 -y && conda activate kafka-debug && pip install -r requirements.txt
conda activate kafka-debug
```

### 3. Kubernetes Deployment

Deploy the application to your Kubernetes cluster:

```bash
kubectl apply -f kube/
```

## Debugging with mirrord

mirrord offers two powerful approaches for debugging Kafka consumers:

### Approach 1: Copy Target with Scale Down

Debug with your local consumer as the only active consumer:

```bash
mirrord exec --config .mirrord/.copy_scaledown.json -- python app.py
```

This configuration:
- Creates a copy of the target deployment's pod
- Scales down the original deployment to zero replicas
- Ensures your local application receives all messages

### Approach 2: Queue Splitting

Debug without disrupting existing consumers:

```bash
APP_MODE=consumer PYTHONUNBUFFERED=1 mirrord exec -f .mirrord/mirrord.json -- python app.py
```

This configuration:
- Allows both your local application and remote consumers to receive the same messages
- Uses the mirrord operator to intercept and duplicate Kafka messages
- Supports message filtering for targeted debugging

## How it Works

mirrord allows you to run your Kafka consumer locally while connecting to your Kubernetes cluster:

- Your local consumer can receive messages from Kafka topics in the cluster
- You can debug your consumer code with local tools while processing real Kafka messages
- Choose between exclusive access to messages or non-disruptive debugging

## Configuration Files

This project includes several mirrord configuration files:

- `.mirrord/mirrord.json`: Configuration for queue splitting
- `.mirrord/.copy_scaledown.json`: Configuration for copy target with scale down

## Additional Documentation

For more detailed information about debugging Kafka consumers with mirrord, refer to the [BLOG.md](BLOG.md) file in this repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details.