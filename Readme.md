# Common Crawl Pipeline

## Setup

```bash
mkdir common-crawl-pipeline
cd common-crawl-pipeline
git init
cargo new pipeline
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


## Ideas

- autometrics
- local rabbitmq server
