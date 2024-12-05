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

    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ["RABBITMQ_CONNECTION_STRING"])
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME)
    return channel
