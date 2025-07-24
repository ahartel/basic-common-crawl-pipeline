from abc import ABC, abstractmethod
import json
import argparse
from typing import Any, Mapping, Sequence
from prometheus_client import Counter, start_http_server

from commoncrawl import (
    BASE_URL,
    CRAWL_PATH,
    CCDownloader,
    CSVIndexReader,
    Downloader,
    IndexReader,
)
from rabbitmq import QUEUE_NAME, MessageQueueChannel, RabbitMQChannel


BATCH_SIZE = 50

COUNTERS = {
    "batches": Counter("batcher_batches", "Number of published batches"),
    "total_docs": Counter("batcher_total_documents", "Total documents processed by the batcher"),
    "non_english": Counter("batcher_non_english_documents", "Documents filtered out for not being English"),
    "non_200": Counter("batcher_non_200_documents", "Documents filtered out for not having status 200"),
    "passed_filter": Counter("batcher_passed_filter_documents", "Documents that passed all filters"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batcher")
    parser.add_argument(
        "--cluster-idx-filename", type=str, help="Input file path", required=True
    )
    return parser.parse_args()


def publish_batch(
    channel: MessageQueueChannel,
    batch: Sequence[Mapping[str, Any]],
) -> None:
    print("Pushing batch of size", len(batch))
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(batch),
    )
    COUNTERS["batches"].inc()


def process_document(metadata: Any, counters: Mapping[str, Counter]) -> bool:
    counters['total_docs'].inc()
    if "languages" not in metadata or "eng" not in metadata["languages"]:
        counters['non_english'].inc()
        return False
    if metadata.get("status") != "200":
        counters['non_200'].inc()
        return False
    counters['passed_filter'].inc()
    return True


def process_index(
    index: IndexReader,
    channel: MessageQueueChannel,
    downloader: Downloader,
    batch_size: int,
) -> None:
    found_urls = []
    for cdx_chunk in index:
        data = downloader.download_and_unzip(
            cdx_chunk[1], int(cdx_chunk[2]), int(cdx_chunk[3])
        ).decode("utf-8")
        for line in data.split("\n"):
            if line == "":
                continue
            values = line.split(" ")
            metadata = json.loads("".join(values[2:]))

            if not process_document(metadata, COUNTERS):
                continue

            found_urls.append(
                {
                    "surt_url": values[0],
                    "timestamp": values[1],
                    "metadata": metadata,
                }
            )
            if len(found_urls) >= batch_size:
                publish_batch(channel, found_urls)
                found_urls = []

    if len(found_urls) > 0:
        publish_batch(channel, found_urls)


def main() -> None:
    args = parse_args()
    start_http_server(9000)
    channel = RabbitMQChannel()
    downloader = CCDownloader(f"{BASE_URL}/{CRAWL_PATH}")
    index_reader = CSVIndexReader(args.cluster_idx_filename)
    process_index(index_reader, channel, downloader, BATCH_SIZE)


if __name__ == "__main__":
    main()
