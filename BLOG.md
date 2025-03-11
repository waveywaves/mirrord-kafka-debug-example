# Debugging Kafka Queues with mirrord

## 1. Introduction to debugging Kafka queues with mirrord

### a. Introduction

Debugging distributed applications, especially those that use messaging queues like Apache Kafka, can be challenging. These systems often span multiple services and depend on asynchronous communication patterns. Traditional debugging approaches can fall short when trying to trace issues across these complex systems.

mirrord is a powerful tool that helps developers debug cloud-native applications by bringing remote resources into your local environment using context mirroring. In this blog post, we'll explore how mirrord can be used to debug Kafka queue-based applications effectively.

### b. Prerequisites

Before we dive into debugging Kafka queues with mirrord, ensure you have the following set up:

#### Development Environment
- A Kubernetes cluster (you can use one of the following):
  - kind (Kubernetes in Docker)
  - minikube
  - Remote cluster with proper access
- kubectl CLI tool installed and configured
- Helm (if using Helm for installation)

#### Installing mirrord

Install the mirrord CLI:

```bash
brew install metalbear-co/mirrord/mirrord
```

For alternative installation methods, please follow the [quick start guide](https://mirrord.dev/docs/overview/quick-start/).

#### Installing mirrord operator

You can install the mirrord operator using either Helm or the CLI:

Using Helm:
```bash
# Add the MetalBear Helm repository
helm repo add metalbear https://metalbear-co.github.io/charts

# Install the chart with Kafka splitting enabled
helm install --set license.key=your-license-key mirrord-operator metalbear/mirrord-operator
```

Or using the CLI:
```bash
mirrord operator setup --accept-tos --license-key your-license-key --kafka-splitting | kubectl apply -f -
```

Note: When installing with the mirrord-operator Helm chart, Kafka splitting is enabled by setting the `operator.kafkaSplitting` value to `true`.

### c. What is a queue and when is it used?

A queue is a data structure that follows the First-In-First-Out (FIFO) principle, where the first element added is the first one to be removed. In distributed systems, message queues like Kafka are used to:

- Decouple services, allowing them to communicate asynchronously
- Handle traffic spikes by buffering messages
- Enable reliable message delivery with persistence and replication
- Support different messaging patterns (publish-subscribe, point-to-point)

Queues are particularly useful in microservices architectures, event-driven systems, data pipelines, and any scenario where you need reliable asynchronous communication between components.

### d. Popular queue services

Several popular message queue services are used in modern distributed applications:

1. **Apache Kafka**: A distributed event streaming platform with high throughput, fault tolerance, and durability
2. **RabbitMQ**: A traditional message broker implementing the AMQP protocol
3. **AWS SQS/SNS**: Amazon's managed queue and notification services
4. **Google Pub/Sub**: Google Cloud's asynchronous messaging service
5. **Azure Service Bus**: Microsoft's fully managed enterprise message broker

This blog post will focus on debugging applications with mirrord that use Apache Kafka.

## 2. Scenarios while debugging a queue

### a. Simple Kafka producer-consumer application example

To demonstrate debugging techniques, we'll use a simple Kafka producer-consumer application. This [example](https://github.com/waveywaves/mirrord-kafka-debug-example) consists of:

- A Kafka broker
- A producer service that publishes messages to a Kafka topic
- A consumer service that reads messages from the same topic

The following architecture diagram assumes that we are deploying our application and Kafka in Kubernetes. This guide is meant to be used along with the [example repo](https://github.com/waveywaves/mirrord-kafka-debug-example) based on which follows the same architecture.

![Architecture Diagram - Setup without mirrord](images/setup%20without%20mirrord.png)

#### i. Understand the application consumer, producer, and Kafka config

Our example application has these components:

**Producer** (`kafka-producer` deployment):
- Flask web application that publishes messages to a Kafka topic
- Exposes an API endpoint for receiving message data
- Uses the confluent-kafka Python library

**Consumer** (`kafka-consumer` deployment):
- Flask web application that reads messages from the Kafka topic
- Processes messages and exposes them via a web interface
- Uses the confluent-kafka Python library

**Kafka Configuration**:
- Single broker Kafka cluster
- Topic: `test-topic`
- Consumer group: `test-consumer-group`

The applications are containerized and deployed to Kubernetes.

#### ii. Table of important values for Kafka endpoint

| Parameter | Value | Description |
|-----------|-------|-------------|
| bootstrap.servers | kafka-0.kafka.default.svc.cluster.local:9092 | Kafka broker address |
| security.protocol | PLAINTEXT | Authentication protocol (no security in this example) |
| client.id | mirrord-operator | Client identifier for the Kafka connection |
| request.timeout.ms | 20000 | Request timeout in milliseconds |
| connections.max.idle.ms | 300000 | Maximum time connections can remain idle |

#### iii. Table of important values for the consumer topic and group id

| Parameter | Value | Description |
|-----------|-------|-------------|
| Topic Name | test-topic | The Kafka topic the consumer subscribes to |
| Group ID | test-consumer-group | Consumer group identifier for the consumer |
| Partition Strategy | Auto (default) | How messages are distributed among consumers |
| Auto Commit | Enabled | Whether offsets are committed automatically |

### b. Ideal scenario while debugging queues

When debugging queue-based applications, the ideal scenario would be:

1. Full visibility into the message flow
2. Ability to intercept messages without affecting production systems
3. Reproducing issues locally with the same environment as production
4. Access to Kafka broker metrics and consumer group information
5. Low latency and real-time monitoring capabilities

mirrord helps create these ideal conditions by connecting your local development environment to your remote Kubernetes cluster.

### c. Problems faced while debugging queues

#### i. The remote consumer competes with the debug consumer

One of the main challenges when debugging Kafka applications is that the remote consumer (running in production/staging) competes with your local debug consumer. Since Kafka distributes messages among consumers in the same consumer group, your debug consumer might not receive all the messages needed for debugging, making it difficult to reproduce issues.

#### ii. Full data redirection from the main consumer to the debug consumer (when using copy_target + scaledown)

Using the `copy_target` feature with `scale_down` option in mirrord, you can ensure all the messages are directed to your local debug consumer. This approach:

1. Creates a copy of the target deployment's pod
2. Scales down the original deployment to zero replicas
3. Uses the copied pod as the target for the mirrord session
4. Ensures your local application receives all the messages

This lets you debug the consumer without any competition from remote consumers.

![Architecture Diagram - Copy Target with Scale Down](images/setup%20with%20mirrord%20copy_target%2Bscaledown.png)

## 3. Debugging a Kafka topic

### a. Simple Debug: Local consumer consumes the data exclusively

#### i. copy_target + scaledown

The simplest way to debug Kafka consumers is to ensure your local consumer is the only one receiving messages from the topic. mirrord's `copy_target` feature with `scale_down` enabled accomplishes this:

```json
{
    "operator": true,
    "target": {
        "deployment": "kafka-consumer",
        "container": "consumer"
    },
    "feature": {
        "copy_target": {
            "scale_down": true
        }
    }
}
```

This configuration:
1. Targets the `kafka-consumer` deployment
2. Creates a copy of the deployment's pod
3. Scales down the original deployment to zero
4. Ensures your local application is the only consumer of the messages

To use this configuration:

```bash
$ kubectl apply -f kube/
```

![Kubernetes Apply Command](images/k%20apply%20-f%20kube%20.png)

```bash
mirrord exec --config .mirrord/.copy_scaledown.json -- python app.py
```

![Terminal Output for Copy Target](images/terminal%20screenshot%20for%20copy_target%20output.png)

![Kafka Producer UI for Copy Target](images/Kafka%20Producer%20UI%20Screenshot%20copy_target.png)

### Queue Splitting: Local and Remote consumers consume the same data

#### i. Introduction to queue splitting

Queue splitting is a feature in mirrord that allows both your local application and the remote application to receive the same messages. This is particularly useful when you want to debug without disrupting the existing remote consumers.

![Architecture Diagram - Queue Splitting Setup 1](images/setup%20with%20mirrord%20queue_splitting%201.png)

![Architecture Diagram - Queue Splitting Setup 2](images/setup%20with%20mirrord%20queue_splitting%202.png)

##### 1. How does queue splitting work with the mirrord operator?

The mirrord operator intercepts messages at the Kafka broker level before they are delivered to consumers. It makes copies of these messages and delivers them to both the remote consumers and your local application. 

This works by:
1. The mirrord operator understands the Kafka protocol
2. It identifies messages being sent to specific topics
3. It duplicates these messages, sending the original to the real consumers and copies to your local application

##### 2. What local mirrord needs to know about the application?

For queue splitting to work, the local mirrord client needs to know:
- The Kafka topic to listen to
- The consumer group ID of your application
- Optional message filters to select specific messages

These can be configured in your mirrord configuration file:

```json
{
    "operator": true,
    "target": {
        "deployment": "kafka-consumer",
        "container": "consumer"
    },
    "feature": {
        "split_queues": {
            "test_topic": {
                "queue_type": "Kafka",
                "message_filter": {
                    "source": "^test-"
                }
            }
        }
    }
}
```

![Terminal Screenshot for Filter Queue Splitting](images/terminal%20screenshot%20for%20filter%20queue_splitting.png)

##### 3. What the operator needs to know about the application

The mirrord operator needs information about:
- The Kafka client configuration (broker addresses, security settings)
- The topics to monitor
- The deployments consuming these topics
- Consumer group mappings

This is configured using Kubernetes custom resources like `MirrordKafkaClientConfig` and `MirrordKafkaTopicsConsumer`:

The `MirrordKafkaClientConfig` has to be in the same repository as where the mirrord operator is running. It needs to have the bootstrap server endpoint and the client id given in the configuration. 

```yaml
apiVersion: queues.mirrord.metalbear.co/v1alpha
kind: MirrordKafkaClientConfig
metadata:
  name: base-config
  namespace: mirrord
spec:
  properties:
  - name: bootstrap.servers
    value: kafka-0.kafka.default.svc.cluster.local:9092
  - name: client.id
    value: mirrord-operator
  - name: security.protocol
    value: PLAINTEXT
```

It is mandatory to create a base-config. For this example we only have the base-config but you can create a basic base config and extend it with the base-config as a parent. Do check [the documentation](https://mirrord.dev/docs/using-mirrord/queue-splitting/#mirrordkafkaclientconfig) for more information on how to extend the base-config.

Through the above configuration we are letting the operator know how to connect to the Kafka cluster. After configuring the above, let's ensure that the operator has information on the consumer workload topics which the local application can use for debugging. For this, let's configure a `MirrordKafkaTopicsConsumer` custom resource which reference the environment variables for the Kafka topic and group id. 

```
apiVersion: queues.mirrord.metalbear.co/v1alpha
kind: MirrordKafkaTopicsConsumer
metadata:
  name: kafka-consumer-topics
  namespace: default
spec:
  consumerApiVersion: apps/v1
  consumerKind: Deployment
  consumerName: kafka-consumer
  topics:
  - id: test_topic
    clientConfig: base-config
    nameSources:
    - directEnvVar:
        container: consumer
        variable: KAFKA_TOPIC
    groupIdSources:
    - directEnvVar:
        container: consumer
        variable: KAFKA_GROUP_ID
```

![Terminal Screenshot for Setup Queue Splitting](images/terminal%20screenshot%20for%20setup%20queue_splitting.png)

#### How to use queue splitting to debug a producer-consumer application in Kafka

##### Prerequisites

###### Kubernetes cluster (mention kind)

You need a Kubernetes cluster to deploy the application and the mirrord operator. For development purposes, you can use:
- kind (Kubernetes in Docker)
- minikube
- Remote cluster with proper access

###### Installing mirrord

To install mirrord CLI:

```bash
brew install metalbear-co/mirrord/mirrord
```

Please follow the [quick start guide](https://mirrord.dev/docs/overview/quick-start/) if the above installation method doesn't work.

###### Installing mirrord operator with Kafka queue splitting enabled

To install the mirrord Operator with Helm, first add the MetalBear Helm repository:

```bash
helm repo add metalbear https://metalbear-co.github.io/charts
```

Then install the chart with Kafka splitting enabled:

```bash
helm install --set license.key=your-license-key mirrord-operator metalbear/mirrord-operator
```

When installing with the mirrord-operator Helm chart, Kafka splitting is enabled by setting the `operator.kafkaSplitting` value to `true`.

Alternatively, you can install the operator using the CLI:

```bash
mirrord operator setup --accept-tos --license-key your-license-key --kafka-splitting | kubectl apply -f -
```

##### Configurations

###### Local application: .mirrord.json

```json
{
    "operator": true,
    "target": {
        "deployment": "kafka-consumer",
        "container": "consumer"
    },
    "feature": {
        "split_queues": {
            "test_topic": {
                "queue_type": "Kafka",
                "message_filter": {
                    "source": "^test-"
                }
            }
        }
    }
}
```

###### Remote application: Operator configuration

Apply the Kubernetes resources for the mirrord operator configuration:

```bash
kubectl apply -f kube/
```

#### Debugging your Kafka queues with mirrord queue splitting

To start debugging with queue splitting:

```bash
# Example output of deploying the application
$ kubectl apply -f kube/
```

Run your local application with mirrord using queue splitting.

```bash
$ APP_MODE=consumer PYTHONUNBUFFERED=1 mirrord exec -f .mirrord/mirrord.json -- python app.py
```

![mirrord Exec Queue Splitting 1](images/mirrord%20exec%20queue_splitting%201.png)

![mirrord Exec Queue Splitting 2](images/mirrord%20exec%20queue_splitting%202.png)

![Kafka Producer UI Screenshot for Queue Splitting](images/Kafka%20Producer%20UI%20Screenshot%20queue_splitting.png)

With this setup, both your local application and the remote consumer will receive the same Kafka messages, allowing you to debug issues without disrupting the production flow.

## Conclusion

Debugging Kafka-based applications brings unique challenges due to their distributed nature and asynchronous communication patterns. mirrord offers powerful capabilities to overcome these challenges:

1. **Queue splitting** allows you to debug without disrupting existing consumers by duplicating messages
2. **Copy target with scale down** gives your local application exclusive access to Kafka messages
3. The ability to filter messages helps focus on specific message patterns

These features enable developers to:
- Reproduce and fix bugs faster
- Test changes in a realistic environment
- Understand message flow in complex distributed systems
- Troubleshoot production issues without disrupting service

By leveraging mirrord, you can significantly improve your productivity when working with Kafka-based applications and streamline your debugging workflow.

For more information, visit the official [mirrord documentation](https://mirrord.dev/docs/). 