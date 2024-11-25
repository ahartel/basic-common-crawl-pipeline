//! The batcher only operates on index files that contain metadata about the URLs that are part of the crawl.
//! It does not have to download the actual content of the URLs and therefore it does not have to deal with WARC files.
//!
//! For a given crawl, there are hundreds of index files, each containing roughly a gigabyte of URL metadata.
//! Every line in the index file contains the following information. Notice that I have split the line into multiple lines for readability:
//!
//! ```json
//! 0,100,22,165)/
//! 20240722120756
//! {
//!     "url": "http://165.22.100.0/",
//!     "mime": "text/html",
//!     "mime-detected": "text/html",
//!     "status": "301",
//!     "digest": "DCNYNIFG5SBRCVS5PCUY4YY2UM2WAQ4R",
//!     "length": "689",
//!     "offset": "3499",
//!     "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/crawldiagnostics/CC-MAIN-20240722095039-20240722125039-00443.warc.gz",
//!     "redirect": "https://157.245.55.71/"
//! }
//! ```
//!
//! The first lines contains the URL in SURT (Sort-friendly URI Reordering Transform) format, the second lines contains the crawl timestamp, and the remaining lines contain JSON metadata.
//!
//! The URLs in the index files are sorted alpha-numerically.
//!
//! Once the batcher has downloaded (parts of) an index file, it will filter out URLs that are not in English or that did not return a 200 HTTP status code, batch them into groups whose size has a constant upper limit and push the messages containing these URls into a RabbitMQ queue.
use anyhow::{Context, Result};
use clap::Parser;
use pipeline::{
    commoncrawl::{download_and_unzip, parse_cdx_line, parse_cluster_idx},
    rabbitmq::{
        publish_batch, rabbitmq_channel_with_queue, rabbitmq_connection, BATCH_SIZE, CC_QUEUE_NAME,
    },
    tracing_and_metrics::{run_metrics_server, setup_tracing},
};
use std::fs;

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    /// For an explanation for why this file needs to be provided, please
    /// see Readme.md, section "Why do we download the cluster.idx file up front?".
    #[arg(short('i'), long("index"), default_value = "cluster.idx")]
    cluster_idx_filename: String,

    /// The dataset to use; the index file should point to the same dataset or it will not work
    #[arg(short('d'), long("dataset"), default_value = "CC-MAIN-2024-30")]
    dataset: String,

    /// This command line argument can be used to limit the number of chunks that should be processed.
    /// If set, the batcher only processes so many lines from the provided cluster.idx file.
    /// Otherwise, it processes all entries in the file.
    #[arg(short('c'), long("chunks"), default_value_t = 1000, 
    value_parser = clap::value_parser!(u64).range(1..=1000))]
    num_cdx_chunks_to_process: u64,
}

#[tokio::main]
async fn main() {
    let run_result = run(Args::parse()).await;
    if let Err(e) = run_result {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

async fn run(args: Args) -> Result<()> {
    setup_tracing();
    tokio::task::spawn(run_metrics_server(9000));

    let rabbit_conn = rabbitmq_connection()
        .await
        .with_context(|| "Looks like rabbit is not available.")?;
    let (channel, _queue) = rabbitmq_channel_with_queue(&rabbit_conn, CC_QUEUE_NAME).await?;

    let idx_filename = args.cluster_idx_filename;
    let idx = fs::read_to_string(&idx_filename)
        .with_context(|| format!("Failed to read idx file from {}", idx_filename))?
        .lines()
        .filter_map(parse_cluster_idx)
        .collect::<Vec<_>>();
    
    tracing::info!("{} index lines logged for processing", idx.len());
    
    let mut num_cdx_chunks_processed = 0usize;
    for cdx_chunk in idx {
        print!(".");
        let english_cdx_entries = String::from_utf8(
            download_and_unzip(
                &format!(
                    "https://data.commoncrawl.org/cc-index/collections/{}/indexes/{}",
                    args.dataset,
                    cdx_chunk.cdx_filename
                ),
                cdx_chunk.cdx_offset,
                cdx_chunk.cdx_length,
            )
            .await?,
        )?
        .lines()
        .map(parse_cdx_line)
        .filter(|e| {
            if let Some(languages) = e.metadata.languages.as_ref() {
                languages.contains("eng") && e.metadata.status == 200
            } else {
                false
            }
        })
        .collect::<Vec<_>>();

        for batch in english_cdx_entries.as_slice().chunks(BATCH_SIZE) {
            publish_batch(&channel, CC_QUEUE_NAME, batch).await;
        }
        num_cdx_chunks_processed += 1;

        if args.num_cdx_chunks_to_process as usize == num_cdx_chunks_processed {
            break;
        }
    }

    Ok(())
}
