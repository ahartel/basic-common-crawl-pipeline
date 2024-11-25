# Common Crawl Pipeline

## Overview

This is a project to teach Rust to students.
It is inspired by a real-world LLM pre-training data filtering pipeline build at [@Aleph-Alpha](https://github.com/Aleph-Alpha/).

The pipeline downloads archived web pages from the Common Crawl dataset and extracts the text from them and applies some filters. To learn more about the Common Crawl dataset, visit https://commoncrawl.org/get-started.
Common Crawl is a non-profit organization that crawls the web and freely provides its archives and datasets to the public.
Common Crawl crawls the web roughly once a month.
For this project, we chose the Common Crawl dataset CC-MAIN-2024-30.

The pipeline currently consists of a batcher and a worker binary.

The batcher downloads index entries for the crawl CC-MAIN-2024-30.
The batcher will filter out non-English entries and non-successful HTTP requests (non-200).
It will then produce URL batches of up to 200 entries and publish them into a RabbitMQ queue.

The worker pulls batches from that RabbitMQ queue and downloads each WARC part in turn.
Then, it extracts the text from the HTML file using the trafilatura Python package.
In its current implementation it does not refine the extracted text in any way nor does it output the extracted text to a file.

The reason why we chose this particular architecture is that it allows us to scale the workers up and down, while only having to deploy a single batcher. 
If we wanted to process another crawl as well, we could simply deploy another batcher. But in practice this is not very efficient since crawls might have a large overlap in URLS. For URLs that show up in multiple crawls, we might only want to keep the most recent version and apply some de-duplication. This is not implemented in this pipeline.

For a more video explaining the background and some details of the project, please see my talk: https://www.youtube.com/watch?v=Moy6kWmx-Os

You might realize that the code in this repository does not contain much structure and error handling.
We have deliberately chosen to leave some open ends because we do occasionally also use this project for coding challenges.

## How does the batcher work?

The batcher only operates on index files that contain metadata about the URLs that are part of the crawl.
It does not have to download the actual content of the URLs and therefore it does not have to deal with WARC files.

For a given crawl, there are hundreds of index files, each containing roughly a gigabyte of URL metadata.
Every line in the index file contains the following information. Notice that I have split the line into multiple lines for readability:

```
0,100,22,165)/
20240722120756
{
    "url": "http://165.22.100.0/",
    "mime": "text/html",
    "mime-detected": "text/html",
    "status": "301",
    "digest": "DCNYNIFG5SBRCVS5PCUY4YY2UM2WAQ4R",
    "length": "689",
    "offset": "3499",
    "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/crawldiagnostics/CC-MAIN-20240722095039-20240722125039-00443.warc.gz",
    "redirect": "https://157.245.55.71/"
}
```

The first lines contains the URL in SURT (Sort-friendly URI Reordering Transform) format, the second lines contains the crawl timestamp, and the remaining lines contain JSON metadata.

The URLs in the index files are sorted alpha-numerically.

Once the batcher has downloaded (parts of) an index file, it will filter out URLs that are not in English or that did not return a 200 HTTP status code, batch them into groups whose size has a constant upper limit and push the messages containing these URls into a RabbitMQ queue.

### How does the worker work?

The worker(s) pull(s) messages from the RabbitMQ queue and downloads the WARC files that contain the actual content of the URLs.
Once the content has been downloaded, the worker extracts the text from the HTML file using the trafilatura Python package.

After having downloaded and extracted the text from the HTML file, the worker could apply some filters to the extracted text.
We would also want to tokenize (for LLM training) the text and output it to a file.

In its current implementation it does not refine or filter the extracted text in any way nor does it output the extracted text to a file.

### Why do we download the cluster.idx file up front?

The batcher could just download the index files one by one and filter and batch URLs from there.
However, for practical reasons, we chose here to download the so-called cluster.idx file up front.
We took this decision to be able to show some progress to the user.

The cluster.idx file contains alpha-numerically sorted URL ranges of all the WARC files in the crawl.
Relying on this file allows us to download parts of the index files and avoids having to download hundreds of megabytes at once.
It would also enable us to download the index files in parallel, but we have not implemented this yet.

This is how this file looks:

```
0,100,22,165)/ 20240722120756   cdx-00000.gz    0       188224  1
101,141,199,66)/robots.txt 20240714155331       cdx-00000.gz    188224  178351  2
104,223,1,100)/ 20240714230020  cdx-00000.gz    366575  178055  3
107,128,254,23)/sites.asp?domain=hydrogenheaters.com 20240725183414     cdx-00000.gz    544630  181599  4
109,77,250,142)/url?q=https://batmanapollo.ru 20240722133024    cdx-00000.gz    726229  181656  5
```

Every row contains the begin of the URL range, a timestamp, the name of the index file, the offset in the index file, the length of the byte range in the index file and an incrementing index into the cluster.idx file itself.

## Prerequisites

- You need to have Docker installed on your machine so that you can run containers
- You need to have Rust and Python installed on your machine

## Setup for Rust and Python

### Install Python dependencies:

```
python -m venv venv
source venv/bin/activate
pip install trafilatura
export PYTHONPATH=venv/lib/python3.<VERSION>/site-packages
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

To login, use the username `guest` and the password `guest`.

The AMQP port is used by our Rust binary to connect to the server.
For this to work, you need to export this:

```bash
export RABBITMQ_CONNECTION_STRING=amqp://localhost:<PORT>
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

## Run the Rust-based pipeline

Run the batcher:

```bash
cargo run --bin batcher -- --cluster-idx-filename <CLUSTER_IDX_FILENAME>
```

Run the worker (the worker can and should be started multiple times):

```bash
cargo run --bin worker
```

## Run the Python-based pipeline

Run the batcher:

```bash
cd python
python batcher.py --cluster-idx-filename <CLUSTER_IDX_FILENAME>
```

Run the worker:

```bash
cd python
python worker.py
```

## Coding challenges

This section summarizes some coding challenges that you might want to try to implement.

- Batcher and worker:
    - Make it possible to pass the version of the crawl as an argument. Currently, it is hardcoded to CC-MAIN-2024-30.
    - Add Prometheus counters that track how many documents we are filtering at every stage. This can be done both in the batcher and in the worker.
- Worker: 
    - Write the extracted and filtered document content to an object store. It should be possible to pass the address of the object store bucket to the worker. If you don't already have an object store bucket lying around, you can spin up a `minio/minio` container for that and pass the object store address to the worker. Which file format would you use to store the entries on the object store?
    - Add tokenization so that we already have tokenized data ready for training on the object store. The Huggingface tokenizers library might be a good starting point.
    - Add some metrics so that we know how much data we are currently downloading and how many batches we have already processed and how many documents we have already processed
    - Can performance be improved by leveraging the tokio async runtime, maybe even using multiple threads if necessary?
    - Add a filter that makes sure that documents are at least 500 characters long and at most 1,000,000 characters long
- Batcher:
    - Can we get rid of the `collect` in the batcher that collects the filtered `CdxEntry`s?
    - Put in some error handling when publishing a batch to RabbitMQ. Can we recover from network issues or timeouts?
    - Add some monitoring for the batcher so that we know which percentage of the cluster.idx file has already been processed and so that we know how many batches have already been pushed
    - Allow support for providing multiple crawls that can be processed by the batcher. This feature allows us to collect more data than would be available from a single crawl. But notice that this feature is only useful if we can make sure that we only download the content of every URL only once. Notice that a URL might show up in multiple crawls over time.


## Learning resources if you are new to Rust

- Rust book can be looked into beforehand: https://doc.rust-lang.org/book/
- 100 exercises to learn Rust: https://github.com/mainmatter/100-exercises-to-learn-rust/tree/main


## Troubleshooting

Using the MacOS system python3 (/usr/bin/python3, as opposed to python installed via homebrew, pyenv, nix, etc.) may result in runtime errors such as `Library not loaded: @rpath/Python3.framework/Versions/3.8/Python3`. These can be resolved with another addition to .cargo/config.toml:

```
[build]
rustflags = [
  "-C", "link-args=-Wl,-rpath,/Library/Developer/CommandLineTools/Library/Frameworks",
]
```

See https://pyo3.rs/v0.21.0/building-and-distribution.html?highlight=rpath#macos for more details.