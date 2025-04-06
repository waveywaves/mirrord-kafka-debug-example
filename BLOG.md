# Debugging Kafka Consumers with mirrord

## Introduction

In this guide, we'll cover how to debug Kafka consumer applications running in a Kubernetes environment using mirrord. You'll learn how to set up mirrord and use it to effectively debug Kafka consumers without the traditional overhead of rebuilding and redeploying your application.

**Tip:** You can use mirrord to debug, test, and troubleshoot your Kafka consumers locally with Kubernetes context, without needing to build or deploy each time you make a change.

Debugging distributed applications, especially those that use messaging systems like Apache Kafka, can be challenging. These systems often span multiple services and depend on asynchronous communication patterns. Traditional debugging approaches can fall short when trying to trace issues across these complex systems.

mirrord is a powerful tool that helps developers debug cloud-native applications by bringing remote resources into your local environment using context mirroring. This allows you to run your Kafka consumer locally while connecting it to your remote Kafka environment.

## Prerequisites

Before we dive into debugging Kafka consumers with mirrord, ensure you have the following set up:

### Environment
- A Kubernetes cluster (you can use one of the following):
  - kind (Kubernetes in Docker)
  - minikube
  - Remote cluster with proper access
- kubectl CLI tool installed and configured
- Helm (if using Helm for installation)

### Installing mirrord

Install the mirrord CLI:

```bash
brew install metalbear-co/mirrord/mirrord
```

For alternative installation methods, please follow the [quick start guide](https://mirrord.dev/docs/overview/quick-start/).

### Installing mirrord operator

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

**Note:** When installing with the mirrord-operator Helm chart, Kafka splitting is enabled by setting the `operator.kafkaSplitting` value to `true`.

## Understanding Kafka in Distributed Systems

### What is a queue and when is it used?

A queue is a data structure that follows the First-In-First-Out (FIFO) principle, where the first element added is the first one to be removed. In distributed systems, message queues like Kafka are used to:

- Decouple services, allowing them to communicate asynchronously
- Handle traffic spikes by buffering messages
- Enable reliable message delivery with persistence and replication
- Support different messaging patterns (publish-subscribe, point-to-point)

Queues are particularly useful in microservices architectures, event-driven systems, data pipelines, and any scenario where you need reliable asynchronous communication between components.

### Popular queue services

Several popular message queue services are used in modern distributed applications:

1. **Apache Kafka**: A distributed event streaming platform with high throughput, fault tolerance, and durability
2. **RabbitMQ**: A traditional message broker implementing the AMQP protocol
3. **AWS SQS/SNS**: Amazon's managed queue and notification services
4. **Google Pub/Sub**: Google Cloud's asynchronous messaging service
5. **Azure Service Bus**: Microsoft's fully managed enterprise message broker

In this guide, we'll focus specifically on debugging applications with mirrord that use Apache Kafka.

## Common debugging techniques for Kafka consumers

It can be cumbersome to debug Kafka consumers on Kubernetes. The lack of a debugging workflow for applications with multiple runtime dependencies in the context of Kubernetes makes it even harder. Why is debugging Kafka consumers in Kubernetes so challenging? Let's look at the common approaches and their limitations:

### Continuous Deployment
Build a container image and deploy it to a Kubernetes cluster dedicated to testing or staging. The iterative process of building, deploying, and testing is resource-intensive and time-consuming, especially when you're making frequent code changes to your Kafka consumers.

### Log Analysis
One of the most common ways to understand Kafka consumer behavior in a cluster is by analyzing logs. Adding extra logs to extract runtime information about message consumption, offsets, and processing is very common. While collecting and analyzing logs from different consumers can be effective, it isn't the best real-time debugging solution, especially when trying to trace message flow through the system.

### Remote Debugging
Developers can use remote debugging tools built into IDEs to attach to Kafka consumer processes already running in a Kubernetes cluster. While this allows real-time code inspection and interaction, it still requires heavy overhead from the IDE and a separate debug configuration for the deployment which can potentially affect the consumer's performance while debugging.

The above methods can be used by themselves or they can be used together, but they all have significant drawbacks in terms of development speed and efficiency.

## Challenges of debugging Kafka consumers in Kubernetes

Debugging Kafka consumers effectively within a Kubernetes context is perhaps the biggest challenge of working with Kafka in cloud environments. The build and release loop of the application can be short, but the process slows down development significantly. Nothing beats the ease and speed of debugging applications locally.

Kafka consumers present unique challenges:

1. **Message Distribution**: Kafka distributes messages among all consumers in a consumer group, making it difficult to ensure your debug consumer sees all relevant messages.

2. **State Management**: Consumers maintain offset state, and debugging can disrupt this state management, leading to missed or duplicate message processing.

3. **Environment Dependencies**: Kafka consumers typically depend on specific configurations for brokers, topics, and security settings that must be replicated in the debug environment.

4. **Performance Implications**: Debugging tools can introduce latency that may trigger rebalancing or timeout issues that don't exist in production.

5. **Distributed Tracing**: Following a message through the entire system from producer to consumer can be challenging without proper tooling.

These challenges make it essential to have a debugging approach that can seamlessly integrate with both local and remote Kafka environments.

## Introduction to debugging Kafka consumers with mirrord

With mirrord, you don't have to think about building and releasing your applications for debugging. You can run your Kafka consumers locally and mirrord will make sure your locally running process has the context of Kubernetes. Context mirroring for processes allows your process to run locally and consume the resources of a remote Kafka environment.

### Workload to process context mirroring

To achieve this, inputs from a Kubernetes workload (e.g., a Kafka consumer Pod) are mirrored to your locally running process. Let's see how we can mirror inputs for our locally running Kafka consumer application using mirrord and pipe these outputs back to Kubernetes. This creates a tighter feedback loop, effectively allowing you to debug faster without the downsides of the common debugging techniques we discussed above.

## Sample application setup

Let's explore how to debug Kafka consumers using a simple example application. Our example consists of:

- A Kafka broker
- A producer service that publishes messages to a Kafka topic
- A consumer service that reads messages from the same topic

**Note:** The sample application used in this guide is available at [https://github.com/waveywaves/mirrord-kakfa-debug-example](https://github.com/waveywaves/mirrord-kakfa-debug-example). This guide is intended to be used alongside the repository, which contains all the code and configuration files needed to follow along.

The following architecture diagram shows the basic setup of our Kafka application in Kubernetes without mirrord. It illustrates how the producer sends messages to the Kafka broker, and how the consumer reads these messages in a standard deployment:

![Architecture Diagram - Setup without mirrord](images/setup%20without%20mirrord.png)

### Understanding the application components

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

### Important Kafka configuration values

#### Kafka endpoint configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| bootstrap.servers | kafka-0.kafka.default.svc.cluster.local:9092 | Kafka broker address |
| security.protocol | PLAINTEXT | Authentication protocol (no security in this example) |
| client.id | mirrord-operator | Client identifier for the Kafka connection |
| request.timeout.ms | 20000 | Request timeout in milliseconds |
| connections.max.idle.ms | 300000 | Maximum time connections can remain idle |

#### Consumer configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| Topic Name | test-topic | The Kafka topic the consumer subscribes to |
| Group ID | test-consumer-group | Consumer group identifier for the consumer |
| Partition Strategy | Auto (default) | How messages are distributed among consumers |
| Auto Commit | Enabled | Whether offsets are committed automatically |

## Deploying the example application

Let's start by deploying our example Kafka application to Kubernetes:

```bash
kubectl apply -f kube/
```

After running this command, you'll see output similar to this:

![Kubernetes Apply Command](images/k%20apply%20-f%20kube%20.png)

This deploys the Kafka broker, producer, and consumer to your Kubernetes cluster. Once everything is up and running, we can proceed with debugging.

## Debugging scenarios for Kafka consumers

When debugging Kafka consumers, you typically want:

1. Full visibility into the message flow
2. Ability to intercept messages without affecting production systems
3. Reproducing issues locally with the same environment as production
4. Access to Kafka broker metrics and consumer group information
5. Low latency and real-time monitoring capabilities

mirrord helps create these ideal conditions by connecting your local development environment to your remote Kubernetes cluster. Let's explore two primary debugging approaches.

### Common problems when debugging Kafka consumers

#### The remote consumer competes with your debug consumer

One of the main challenges when debugging Kafka applications is that the remote consumer (running in production/staging) competes with your local debug consumer. Since Kafka distributes messages among consumers in the same consumer group, your debug consumer might not receive all the messages needed for debugging, making it difficult to reproduce issues.

**Tip:** You'll need a way to ensure your debug consumer can see all relevant messages without disrupting production traffic. mirrord offers two approaches to solve this problem.

## Debugging a Kafka consumer with mirrord

Let's dive into two effective approaches for debugging Kafka consumers with mirrord:

### Approach 1: Simple Debug with copy_target + scaledown

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
3. Scales down the original deployment to zero replicas
4. Ensures your local application receives all the messages

This approach is illustrated in the following diagram:

![Architecture Diagram - Copy Target with Scale Down](images/setup%20with%20mirrord%20copy_target%2Bscaledown.png)

#### How to use this configuration

Save the configuration to a file named `.mirrord/.copy_scaledown.json` and run:

```bash
mirrord exec --config .mirrord/.copy_scaledown.json -- python app.py
```

When you run this command, you'll see output similar to:

![Terminal Output for Copy Target](images/terminal%20screenshot%20for%20copy_target%20output.png)

Now your local consumer is receiving all messages since it's the only consumer active. You can send messages using the producer UI:

![Kafka Producer UI for Copy Target](images/Kafka%20Producer%20UI%20Screenshot%20copy_target.png)

**Tip:** This approach is perfect for isolated debugging, but be aware that it temporarily stops the original consumer from processing messages. Use it in development or testing environments rather than production.

### Approach 2: Queue Splitting for non-disruptive debugging

Queue splitting is a powerful feature in mirrord that allows both your local application and the remote application to receive the same messages. This is particularly useful when you want to debug without disrupting the existing remote consumers.

#### How queue splitting works

The following diagrams illustrate how queue splitting works in mirrord:

Initial setup with the mirrord operator intercepting messages:
![Architecture Diagram - Queue Splitting with single debug consumer](images/setup%20with%20mirrord%20queue_splitting%201.png)
<!-- 
Messages are duplicated and delivered to both remote and multiple consumers:
![Architecture Diagram - Queue Splitting setup with two debug consumers](images/setup%20with%20mirrord%20queue_splitting%202.png) -->

This architecture allows multiple debug consumers to run simultaneously. Each developer can run their own local consumer, and all will receive copies of the same messages. The mirrord operator ensures that each local debug consumer gets a complete copy of the message stream, without any competition between them or with the production consumers.

**Tip:** This means your entire team can debug the same Kafka consumer application simultaneously without interfering with each other or with production traffic!

#### Behind the scenes

The mirrord operator intercepts messages at the Kafka broker level before they are delivered to consumers. It makes copies of these messages and delivers them to both the remote consumers and your local application. 

This works by:
1. The mirrord operator understands the Kafka protocol
2. It identifies messages being sent to specific topics
3. It duplicates these messages, sending the original to the real consumers and copies to your local application

When multiple debug consumers are active, the mirrord operator creates temporary queues for each one. Each developer gets their own independent debug session with access to the message stream.

#### Configuration for queue splitting

For queue splitting to work, you need to configure both the local mirrord client and the mirrord operator.

##### Local mirrord configuration

Create a file named `.mirrord/mirrord.json` with the following content:

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

This configuration tells the local mirrord client:
- The Kafka topic to listen to (`test_topic`)
- To filter messages based on a pattern (`^test-`)
- Which deployment to target (`kafka-consumer`)

**Tip:** You can use message filters to focus on specific patterns of messages, making debugging more targeted.

When you run mirrord with message filtering, you'll see output like this:

![Terminal Screenshot for Filter Queue Splitting](images/terminal%20screenshot%20for%20filter%20queue_splitting.png)

##### Operator configuration

The mirrord operator needs information about the Kafka setup. This is configured using Kubernetes custom resources.

First, create a `MirrordKafkaClientConfig` resource:

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

Next, create a `MirrordKafkaTopicsConsumer` resource:

```yaml
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

Apply these configurations to your cluster:

```bash
kubectl apply -f kube/
```

Setting up the mirrord operator for queue splitting will look like this:

![Terminal Screenshot for Setup Queue Splitting](images/terminal%20screenshot%20for%20setup%20queue_splitting.png)

#### Running your local consumer with queue splitting

Now you can run your local application with mirrord using queue splitting:

```bash
APP_MODE=consumer PYTHONUNBUFFERED=1 mirrord exec -f .mirrord/mirrord.json -- python app.py
```

You'll see the initial connection and setup:

![mirrord Exec Queue Splitting 1](images/mirrord%20exec%20queue_splitting%201.png)

And the ongoing operation where mutliple and remote consumers are receiving messages:

![mirrord Exec Queue Splitting 2](images/mirrord%20exec%20queue_splitting%202.png)

The terminal screenshots above show multiple mirrord debug sessions running at the same time. Each instance creates its own copy pod and receives the same messages, demonstrating how multiple developers can debug simultaneously. Notice in the second screenshot how multiple debug consumers are actively receiving messages in parallel.

You can send messages using the producer UI, and both your local and remote consumers will receive copies of these messages:

![Kafka Producer UI Screenshot for Queue Splitting](images/Kafka%20Producer%20UI%20Screenshot%20queue_splitting.png)

**Tip:** Queue splitting is ideal for team environments where multiple developers need to debug the same Kafka consumer application simultaneously. It provides a non-disruptive way for everyone to see the full message stream without affecting production systems.

## Debugging with mirrord vs. other debugging techniques

mirrord distinguishes itself by eliminating the need for repeated building and deployment cycles. It allows you to run your Kafka consumer locally while providing it with the necessary network and execution context of the target Kubernetes environment. Your local consumer behaves as if it were running within the cluster, enabling you to debug using familiar tools without the overhead of build and deploy cycles.

## Conclusion

In this guide, we've explored how to use mirrord to debug Kafka consumer applications in Kubernetes. We've seen two powerful approaches:

1. **Queue splitting** allows you to debug without disrupting existing consumers by duplicating messages
2. **Copy target with scale down** gives your local application exclusive access to Kafka messages

By leveraging mirrord, you can significantly improve your productivity when working with Kafka consumer applications and streamline your debugging workflow.

Curious to try it out? Give mirrord a go and see how it works for you. Got questions? Visit the official [mirrord documentation](https://mirrord.dev/docs/) or join the community Discord channel! 