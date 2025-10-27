from abc import ABC, abstractmethod
import os
import pika


QUEUE_NAME = "batches"


class MessageQueueChannel(ABC):
    @abstractmethod
    def basic_publish(self, exchange: str, routing_key: str, body: str) -> None:
        pass


class RabbitMQChannel(MessageQueueChannel):
    def __init__(self) -> None:
        self.channel = rabbitmq_channel()

    def basic_publish(self, exchange: str, routing_key: str, body: str) -> None:
        self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
        )


def rabbitmq_channel() -> pika.adapters.blocking_connection.BlockingChannel:
    # Get connection parameters from environment
    if "RABBITMQ_CONNECTION_STRING" in os.environ:
        connection_string = os.environ["RABBITMQ_CONNECTION_STRING"]
    else:
        # Build connection string from individual components
        host = os.getenv("RABBITMQ_HOST", "localhost")
        port = os.getenv("RABBITMQ_PORT", "5672")
        user = os.getenv("RABBITMQ_USER", "guest")
        password = os.getenv("RABBITMQ_PASSWORD", "guest")
        connection_string = f"amqp://{user}:{password}@{host}:{port}/"
    
    connection = pika.BlockingConnection(
        pika.URLParameters(connection_string)
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME)
    return channel
