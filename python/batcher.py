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
total_documents_counter = Counter("batcher_total_documents", "Total documents processed")

# Language filtering counters
no_language_info_counter = Counter("batcher_no_language_info", "Documents without language information")
non_english_counter = Counter("batcher_non_english", "Non-English documents filtered out")
english_documents_counter = Counter("batcher_english_documents", "English documents")

# Status filtering counters
non_200_status_counter = Counter("batcher_non_200_status", "Documents with non-200 status filtered out")
status_200_counter = Counter("batcher_status_200", "Documents with status 200")

# Combined filters
urls_in_batches_counter = Counter("batcher_urls_sent", "Total URLs sent in batches")


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
            total_documents_counter.inc()
            metadata = json.loads("".join(values[2:]))

            is_english = False
            if "languages" in metadata:
                if "eng" in metadata["languages"]:
                    is_english = True
                    english_documents_counter.inc()
                else:
                    non_english_counter.inc()
            else:
                no_language_info_counter.inc()

            is_status_200 = False
            if metadata.get("status") == "200":
                is_status_200 = True
                status_200_counter.inc()
            else:
                non_200_status_counter.inc()
            
            # Apply filters: English only AND status 200 only
            if is_english and is_status_200:
                found_urls.append(
                    {
                        "surt_url": values[0],
                        "timestamp": values[1],
                        "metadata": metadata,
                    }
                )
                urls_in_batches_counter.inc()
                    
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
