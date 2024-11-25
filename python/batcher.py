import json
import csv
import argparse

from commoncrawl import download_and_unzip
from rabbitmq import QUEUE_NAME, rabbitmq_channel


BASE_URL = "https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2024-30/indexes"
BATCH_SIZE = 50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batcher")
    parser.add_argument(
        "--cluster-index-filename", type=str, help="Input file path", required=True
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    channel = rabbitmq_channel()

    with open(args.cluster_index_filename, "r") as csvfile:
        index_reader = csv.reader(csvfile, delimiter="\t")
        for cdx_chunk in index_reader:
            data = download_and_unzip(
                f"{BASE_URL}/{cdx_chunk[1]}", int(cdx_chunk[2]), int(cdx_chunk[3])
            ).decode("utf-8")
            found_urls = []
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
                if len(found_urls) >= BATCH_SIZE:
                    print("Pushing batch of size", len(found_urls))
                    channel.basic_publish(
                        exchange="",
                        routing_key=QUEUE_NAME,
                        body=json.dumps(found_urls),
                    )
                    found_urls = []

        if len(found_urls) > 0:
            print("Pushing batch of size", len(found_urls))
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(found_urls),
            )


if __name__ == "__main__":
    main()
