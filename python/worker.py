import io
import os
import json

from prometheus_client import start_http_server, Counter
import trafilatura
from warcio.archiveiterator import WARCIterator
from tokenizers import Tokenizer

from commoncrawl import BASE_URL, CCDownloader, Downloader
from rabbitmq import QUEUE_NAME, rabbitmq_channel
from storage import MinioStorageBackend, get_minio_client
from uploader import ParquetUploader


COUNTERS = {
    "batches": Counter("worker_batches", "Number of consumed batches"),
    "invalid_records": Counter("worker_invalid_records", "Number of invalid records"),
    "total_records": Counter("worker_total_records", "Total number of records"),
}

tokenizer = Tokenizer.from_pretrained("gpt2")


def process_batch(downloader: Downloader, ch, method, _properties, body, uploader):
    print("Received batch of size", len(body))
    batch = json.loads(body)
    documents = []
    for item in batch:
        data = downloader.download_and_unzip(
            item["metadata"]["filename"],
            int(item["metadata"]["offset"]),
            int(item["metadata"]["length"]),
        )
        for record in WARCIterator(io.BytesIO(data)):
            if record.rec_type == "response":
                _text = trafilatura.extract(record.content_stream().read())
                if _text and 1000000 > len(_text) > 500:
                    token_ids = tokenizer.encode(_text).ids
                    documents.append({
                        "surt_url": item["surt_url"],
                        "url": item["metadata"]["url"],
                        "token_ids": token_ids,
                        "filename": item["metadata"]["filename"],
                        "offset": item["metadata"]["offset"],
                        "length": item["metadata"]["length"],
                    })
                else:
                    COUNTERS["invalid_records"].inc()
            else:
                COUNTERS["invalid_records"].inc()
            COUNTERS["total_records"].inc()
    if documents:
        object_name = f"batch_{method.delivery_tag}" + uploader.extension
        uploader.upload(object_name, documents)
    COUNTERS["batches"].inc()
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    start_http_server(9001)
    downloader = CCDownloader(BASE_URL)
    # TODO: use env variables
    minio_client = get_minio_client("localhost:5000", "root", "password")
    storage_backend = MinioStorageBackend(minio_client, "test")
    parquet_uploader = ParquetUploader(storage_backend)
    channel = rabbitmq_channel()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=lambda ch, method, properties, body: process_batch(
            downloader, ch, method, properties, body, parquet_uploader
        ),
    )
    channel.start_consuming()


if __name__ == "__main__":
    main()
