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

batch_counter = Counter("batcher_batches", "Number of published batches")

# Prometheus counters for filtering stages
total_docs_counter = Counter("batcher_total_documents", "Total documents processed by the batcher")
non_english_counter = Counter("batcher_non_english_documents", "Documents filtered out for not being English")
non_200_counter = Counter("batcher_non_200_documents", "Documents filtered out for not having status 200")
passed_filter_counter = Counter("batcher_passed_filter_documents", "Documents that passed all filters")


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
    batch_counter.inc()


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

            total_docs_counter.inc()
            if "languages" not in metadata or "eng" not in metadata["languages"]:
                non_english_counter.inc()
                continue
            if metadata["status"] != "200":
                non_200_counter.inc()
                continue
            passed_filter_counter.inc()

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
