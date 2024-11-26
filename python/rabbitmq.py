import os
import pika


QUEUE_NAME = "batches"


def rabbitmq_channel() -> pika.adapters.blocking_connection.BlockingChannel:
    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ["RABBITMQ_CONNECTION_STRING"])
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME)
    return channel
