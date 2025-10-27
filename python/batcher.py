from abc import ABC, abstractmethod
import json
import argparse
import logging
import os
from typing import Any, Mapping, Sequence
from prometheus_client import Counter, start_http_server

from commoncrawl import (
    BASE_URL,
    CRAWL_PATH,
    CCDownloader,
    CSVIndexReader,
    Downloader,
    IndexReader,
    download_cluster_idx,
)
from rabbitmq import QUEUE_NAME, MessageQueueChannel, RabbitMQChannel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv("BATCHER_BATCH_SIZE", os.getenv("BATCH_SIZE", "50")))

batch_counter = Counter("batcher_batches", "Number of published batches")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batcher")
    parser.add_argument(
        "--cluster-idx-filename", 
        type=str, 
        help="Input file path", 
        required=False
    )
    return parser.parse_args()


def publish_batch(
    channel: MessageQueueChannel,
    batch: Sequence[Mapping[str, Any]],
) -> None:
    logger.info("Pushing batch of size %d", len(batch))
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
            if (
                "languages" in metadata
                and "eng" in metadata["languages"]
                and metadata["status"] == "200"
            ):
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
    prometheus_port = int(os.getenv("BATCHER_METRICS_PORT", os.getenv("PROMETHEUS_PORT", "9000")))
    start_http_server(prometheus_port)
    
    # Get cluster index filename from argument or environment variable
    cluster_idx_filename = args.cluster_idx_filename or os.getenv("CLUSTER_IDX_FILENAME")
    
    if not cluster_idx_filename:
        raise ValueError("cluster.idx filename required via --cluster-idx-filename or CLUSTER_IDX_FILENAME env var")
    
    # In production: auto-download if file doesn't exist
    if not os.path.exists(cluster_idx_filename):
        crawl_version = os.getenv("COMMONCRAWL_VERSION")
        if crawl_version:
            download_cluster_idx(crawl_version, cluster_idx_filename)
    
    channel = RabbitMQChannel()
    downloader = CCDownloader(f"{BASE_URL}/{CRAWL_PATH}")
    index_reader = CSVIndexReader(cluster_idx_filename)
    process_index(index_reader, channel, downloader, BATCH_SIZE)


if __name__ == "__main__":
    main()
