import io
import json
import logging
import os
from prometheus_client import start_http_server
import trafilatura
from warcio.archiveiterator import WARCIterator
from prometheus_client import Counter


from commoncrawl import BASE_URL, CCDownloader, Downloader
from rabbitmq import QUEUE_NAME, rabbitmq_channel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

batch_counter = Counter("worker_batches", "Number of consumed batches")


def process_batch(downloader: Downloader, ch, method, _properties, body):
    logger.info("Received batch of size %d", len(body))
    batch = json.loads(body)
    
    for item in batch:
        data = downloader.download_and_unzip(
            item["metadata"]["filename"],
            int(item["metadata"]["offset"]),
            int(item["metadata"]["length"]),
        )
        for record in WARCIterator(io.BytesIO(data)):
            if record.rec_type == "response":
                _text = trafilatura.extract(record.content_stream().read())
                # TODO: process text with constraints
    batch_counter.inc()
    logger.info("Processed batch successfully")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    prometheus_port = int(os.getenv("WORKER_METRICS_PORT", os.getenv("PROMETHEUS_PORT", "9001")))
    start_http_server(prometheus_port)
    logger.info("Started worker metrics server on port %d", prometheus_port)
    
    downloader = CCDownloader(BASE_URL)
    logger.info("Connecting to RabbitMQ queue: %s", QUEUE_NAME)
    channel = rabbitmq_channel()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=lambda ch, method, properties, body: process_batch(
            downloader, ch, method, properties, body
        ),
    )
    logger.info("Worker started, waiting for messages...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
