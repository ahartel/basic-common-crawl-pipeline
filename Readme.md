# Common Crawl Pipeline

This is a project to teach Rust to students.
It is inspired by a real-world LLM pre-training data filtering pipeline build at Aleph Alpha.

The pipeline currently consists of a batcher and a worker binary.

The batcher downloads index entries for a hard-coded crawl.
This is the crawl CC-MAIN-2024-30.
The batcher will filter out non-English entries and non-successful HTTP requests (non-200).
It will then produce URL batches of up to 200 entries and publish them into a RabbitMQ queue.

The worker pulls batches from that RabbitMQ queue and downloads each WARC part in turn.
Then, it extracts the text from the HTML file using the trafilatura Python package.
It does currently not refine the extracted text in any way nor output the extracted text to a file.

## Setup

### Install Python dependencies:
```
python -m venv venv
source venv/bin/activate
pip install trafilatura
export PYTHONPATH=venv/lib/python3.*/site-packages
```

### Prepare rabbitMQ server

Start the server like this:

```bash
docker run -d -P --name rabbitmq rabbitmq:management
```

Find out which port maps to the management interface (15672) and the AMQP port (5672):
```bash
docker ps
```

Remember both ports. The management interface is useful for debugging and monitoring the queue.
This can be used by pointing your browser to `localhost:PORT`.

The AMQP port is used by our Rust binary to connect to the server.
For this to work, you need to export this:

```bash
export RABBITMQ_CONNECTION_STRING=amqp://localhost:PORT
```

### Install and start metrics server

```bash
brew install autometrics-dev/tap/am
am start http://localhost:9000 http://localhost:9001
```

### Download cluster.idx file and start pipeline

First, we download the Common Crawl index file for one crawl:
```bash
wget https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2024-30/indexes/cluster.idx
```

Run the batcher:
```bash
cargo run --bin batcher -- --cluster-idx-filename <CLUSTER_IDX_FILENAME>
```

Run the worker (the worker can and should be started multiple times):
```bash
cargo run --bin worker
```

## Why do we download the cluster.idx file up front?

This file contains the alphabetical URL ranges of all the WARC files in the crawl.
This is not strictly necessary for our case, but it helps with downloading smaller
file chunks so that we can actually see some progress.

This is how this file looks:
```
0,100,22,165)/ 20240722120756   cdx-00000.gz    0       188224  1
101,141,199,66)/robots.txt 20240714155331       cdx-00000.gz    188224  178351  2
104,223,1,100)/ 20240714230020  cdx-00000.gz    366575  178055  3
107,128,254,23)/sites.asp?domain=hydrogenheaters.com 20240725183414     cdx-00000.gz    544630  181599  4
109,77,250,142)/url?q=https://batmanapollo.ru 20240722133024    cdx-00000.gz    726229  181656  5
```


## Requirements for students

- Docker installed on their machine so that they can run containers
- Rust book can be looked into beforehand: https://doc.rust-lang.org/book/
- 100 exercises to learn Rust: https://github.com/mainmatter/100-exercises-to-learn-rust/tree/main
