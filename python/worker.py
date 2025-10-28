import io
import json
import os
from prometheus_client import start_http_server
import trafilatura
from warcio.archiveiterator import WARCIterator
from prometheus_client import Counter
import pandas as pd
from commoncrawl import BASE_URL, CCDownloader, Downloader
from rabbitmq import QUEUE_NAME, rabbitmq_channel
from pipelines.pipeline import create_full_pipeline, run_pipeline
from parquet_buffer import ParquetBuffer


batch_counter = Counter("worker_batches", "Number of consumed batches")
document_counter_in_process = Counter("worker_documents_in_process", "Number of processed documents")
discarded_documents_counter = Counter("worker_discarded_documents", "Number of discarded documents")
filtered_documents_counter = Counter("worker_filtered_documents", "Number of filtered documents")

def process_batch(downloader: Downloader, ch, method, _properties, body):
    print("Received batch of size", len(body))
    batch = json.loads(body)
    parquet_buffer = ParquetBuffer()
    print(f"Batch size: {len(batch)}")
    for item in batch:
        data = downloader.download_and_unzip(
            item["metadata"]["filename"],
            int(item["metadata"]["offset"]),
            int(item["metadata"]["length"]),
        )
        crawled_text = []
        for record in WARCIterator(io.BytesIO(data)):
            if record.rec_type == "response":
                document_counter_in_process.inc()
                _text = trafilatura.extract(record.content_stream().read())
                if _text:
                   _text = " ".join(filter_text(_text))
                   print(f"Filtered text: {_text}")

                if not _text:
                    discarded_documents_counter.inc()
                    continue
                crawled_text.append(_text)
                filtered_documents_counter.inc()
        
        if crawled_text:
            file_prefix = os.path.splitext(os.path.basename(item["metadata"]["filename"]))[0]
            filename = f"{file_prefix}.parquet"
            item["text"], item["object_name"] = " ".join(crawled_text), filename

            parquet_buffer.add_record(item)

    parquet_buffer.flush()
    batch_counter.inc()
    ch.basic_ack(delivery_tag=method.delivery_tag)

def filter_text(text):
   pipeline = create_full_pipeline()
   return run_pipeline(text, pipeline)

def main() -> None:
    start_http_server(9001)
    downloader = CCDownloader(BASE_URL)
    channel = rabbitmq_channel()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=lambda ch, method, properties, body: process_batch(
            downloader, ch, method, properties, body
        ),
    )
    channel.start_consuming()


if __name__ == "__main__":
    main()
