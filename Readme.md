# Common Crawl Pipeline

## Setup

```bash
mkdir common-crawl-pipeline
cd common-crawl-pipeline
git init
cargo new pipeline
cd pipeline
mkdir src/bin
cp src/main.rs src/bin/batcher.rs
cp src/main.rs src/bin/worker.rs
```

## Steps

First, we download the Common Crawl index file for one crawl:
https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2024-30/indexes/cluster.idx.

This file contains the alphabetical URL ranges of all the WARC files in the crawl.
I think this might not be necessary for our case. Seems to become relevant once we want to
scale up to multiple crawls.

```
0,100,22,165)/ 20240722120756   cdx-00000.gz    0       188224  1
101,141,199,66)/robots.txt 20240714155331       cdx-00000.gz    188224  178351  2
104,223,1,100)/ 20240714230020  cdx-00000.gz    366575  178055  3
107,128,254,23)/sites.asp?domain=hydrogenheaters.com 20240725183414     cdx-00000.gz    544630  181599  4
109,77,250,142)/url?q=https://batmanapollo.ru 20240722133024    cdx-00000.gz    726229  181656  5
```

Therefore, the first thing our code needs to do is to download the actual cdx files from the crawl.
To find out which of these files there are, we must download this file:
https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-30/cc-index.paths.gz

Use the `reqwest` crate to download the file, the `flate2` crate to unzip and `tokio` as async runtime.

```bash
cargo add flate2
cargo add reqwest
cargo add tokio --features macros,rt-multi-thread
```

## Prepare rabbitMQ server

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

## Requirements for students

- Docker installed on their machine so that they can run containers
- Rust book can be looked into beforehand: https://doc.rust-lang.org/book/
- 100 exercises to learn Rust: https://github.com/mainmatter/100-exercises-to-learn-rust/tree/main


## Ideas

I think I should start the day with a presentation that gives an overview over common crawl
and the goal of the pipeline. I can basically reuse my presentation from Berlin.

After that introduction I can set up a rust project and show them how I would start such a project.
This should only take one hour. I can just paste the code to download and unzip a file into main.
Then I realize that I want to do this more often and can therefore refactor.
Then I can realize that I can reuse the client and make a structure with member functions.

Later during the project, the students should set up the following things for metrics and message passing:

- autometrics

To motivate autometrics and metrics collection in general, I should add a screenshot of our
Grafana dashboard to my presentation.

- local rabbitmq server

This is for inter-process communication and should become clear from the architecture diagram.