import io
import json
import argparse
import os
from prometheus_client import start_http_server
import trafilatura
from warcio.archiveiterator import WARCIterator
from prometheus_client import Counter

from commoncrawl import BASE_URL, CCDownloader, Downloader
from minio_consumer import (
    MinioStorage,
    MINIO_URL,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    Storage,
)
from rabbitmq import QUEUE_NAME, rabbitmq_channel

# XXX: use int(os.getenv("DOC_MAX_SIZE", 1_000_000)) if we want it configurable
DOC_MAX_SIZE = 1_000_000
DOC_MIN_SIZE = 500

batch_counter = Counter("worker_batches", "Number of consumed batches")
documents_filtered_worker_too_small = Counter(
    "worker_documents_filtered_too_small", "Number of documents too small in worker"
)
documents_filtered_worker_too_large = Counter(
    "worker_documents_filtered_too_large", "Number of documents too large in worker"
)
documents_filtered_worker_empty_text = Counter(
    "worker_documents_filtered_text_empty",
    "Number of documents with empty text in worker",
)


def process_batch(
    downloader: Downloader, storage: Storage, ch, method, _properties, body
):
    print("Received batch of size", len(body))
    batch = json.loads(body)
    for item in batch:
        data = downloader.download_and_unzip(
            item["metadata"]["filename"],
            int(item["metadata"]["offset"]),
            int(item["metadata"]["length"]),
        )
        for record in WARCIterator(io.BytesIO(data)):
            if record.rec_type == "response":
                text = trafilatura.extract(record.content_stream().read())

                if not text:
                    print("Filtered out document with empty text")
                    documents_filtered_worker_empty_text.inc()
                    continue

                if len(text) < DOC_MIN_SIZE:
                    print("Filtered out too smal document of of size", len(text))
                    documents_filtered_worker_too_small.inc()
                    continue

                if len(text) > DOC_MAX_SIZE:
                    print("Filtered out too large document of of size", len(text))
                    documents_filtered_worker_too_large.inc()
                    continue

                storage.store(
                    {
                        "bucket": "default_bucket",
                        "object_name": item["metadata"]["filename"],
                    },
                    text,
                )

    batch_counter.inc()
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    start_http_server(9001)
    downloader = CCDownloader(BASE_URL)
    storage = MinioStorage(MINIO_URL, MINIO_ACCESS_KEY, MINIO_SECRET_KEY)
    channel = rabbitmq_channel()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=lambda ch, method, properties, body: process_batch(
            downloader, storage, ch, method, properties, body
        ),
    )
    channel.start_consuming()


if __name__ == "__main__":
    main()
