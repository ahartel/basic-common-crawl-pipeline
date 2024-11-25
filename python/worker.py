import io
import json
from prometheus_client import start_http_server
import trafilatura
from warcio.archiveiterator import WARCIterator
from prometheus_client import Counter

from commoncrawl import download_and_unzip
from rabbitmq import QUEUE_NAME, rabbitmq_channel

BASE_URL = "https://data.commoncrawl.org"

batch_counter = Counter("worker_batches", "Number of consumed batches")


def process_batch(ch, method, properties, body):
    print("Received batch of size", len(body))
    batch = json.loads(body)
    for item in batch:
        data = download_and_unzip(
            f"{BASE_URL}/{item['metadata']['filename']}",
            int(item["metadata"]["offset"]),
            int(item["metadata"]["length"]),
        )
        for record in WARCIterator(io.BytesIO(data)):
            if record.rec_type == "response":
                _text = trafilatura.extract(record.content_stream().read())
                # TODO: process text
    batch_counter.inc()
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    channel = rabbitmq_channel()
    start_http_server(9001)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_batch)
    channel.start_consuming()


if __name__ == "__main__":
    main()
