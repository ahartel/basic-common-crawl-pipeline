use anyhow::Context;
use clap::Parser;
use lapin::{options::BasicPublishOptions, BasicProperties};
use pipeline::{
    cdx::{download_and_unzip, CdxEntry},
    rabbitmq::{rabbitmq_channel_with_queue, rabbitmq_connection, BATCH_SIZE, CC_QUEUE_NAME},
    tracing_and_metrics::{run_metrics_server, setup_tracing},
};
use std::fs;

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    #[arg(short, long, default_value = "cluster.idx")]
    cluster_idx_filename: String,

    #[arg(short, long)]
    num_cdx_chunks_to_process: Option<usize>,
}

#[tokio::main]
async fn main() {
    let args = Args::parse();
    setup_tracing();
    tokio::task::spawn(run_metrics_server(9000));

    let rabbit_conn = rabbitmq_connection().await.unwrap();
    let (channel, _queue) = rabbitmq_channel_with_queue(&rabbit_conn, CC_QUEUE_NAME)
        .await
        .unwrap();

    let idx = fs::read_to_string(args.cluster_idx_filename)
        .expect("Should have been able to read the file")
        .lines()
        .filter_map(parse_cluster_idx)
        .collect::<Vec<_>>();

    let mut num_cdx_chunks_processed: usize = 0;
    for cdx_chunk in idx {
        print!(".");
        let english_cdx_entries = String::from_utf8(
            download_and_unzip(
                &format!(
                    "https://data.commoncrawl.org/cc-index/collections/CC-MAIN-2024-30/indexes/{}",
                    cdx_chunk.cdx_filename
                ),
                cdx_chunk.cdx_offset,
                cdx_chunk.cdx_length,
            )
            .await
            .unwrap(),
        )
        .unwrap()
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
            tracing::info!("Sending a batch of {} entries", batch.len());
            channel
                .basic_publish(
                    "",
                    CC_QUEUE_NAME,
                    BasicPublishOptions::default(),
                    &serde_json::to_vec(&batch).unwrap(),
                    BasicProperties::default(),
                )
                .await
                .context("rabbitmq basic publish")
                .unwrap();
        }
        num_cdx_chunks_processed += 1;
        if let Some(to_process) = args.num_cdx_chunks_to_process {
            if to_process == num_cdx_chunks_processed {
                break;
            }
        }
    }
}

fn parse_cdx_line(line: &str) -> CdxEntry {
    let mut parts = line.splitn(3, ' ');
    CdxEntry {
        surt_url: parts.next().unwrap().to_string(),
        timestamp: parts.next().unwrap().to_string(),
        metadata: serde_json::from_str(parts.next().unwrap()).unwrap(),
    }
}

struct ClusterIdxEntry {
    _surt_url: String,
    _timestamp: String,
    cdx_filename: String,
    cdx_offset: usize,
    cdx_length: usize,
    _cluster_id: String,
}

fn parse_cluster_idx(line: &str) -> Option<ClusterIdxEntry> {
    let mut idx = line.split_whitespace();
    Some(ClusterIdxEntry {
        _surt_url: idx.next()?.to_string(),
        _timestamp: idx.next()?.to_string(),
        cdx_filename: idx.next()?.to_string(),
        cdx_offset: idx.next()?.parse().unwrap(),
        cdx_length: idx.next()?.parse().unwrap(),
        _cluster_id: idx.next()?.to_string(),
    })
}

#[cfg(test)]
mod tests {
    use crate::{parse_cdx_line, parse_cluster_idx};

    #[test]
    fn can_parse_cdx_file() {
        let content = r#"0,100,22,165)/ 20240722120756 {"url": "http://165.22.100.0/", "mime": "text/html", "mime-detected": "text/html", "status": "301", "digest": "DCNYNIFG5SBRCVS5PCUY4YY2UM2WAQ4R", "length": "689", "offset": "3499", "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/crawldiagnostics/CC-MAIN-20240722095039-20240722125039-00443.warc.gz", "redirect": "https://157.245.55.71/"}
0,100,22,165)/robots.txt 20240722120755 {"url": "http://165.22.100.0/robots.txt", "mime": "text/html", "mime-detected": "text/html", "status": "301", "digest": "LYEE2BXON4MCQCP5FDVDNILOWBKCZZ6G", "length": "700", "offset": "4656", "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/robotstxt/CC-MAIN-20240722095039-20240722125039-00410.warc.gz", "redirect": "https://157.245.55.71/robots.txt"}
0,100,59,139)/ 20240723213521 {"url": "https://139.59.100.0/", "mime": "text/html", "mime-detected": "text/html", "status": "200", "digest": "5JOQMMSNM6N7UCLGGYXDSPSB3FYAQS2C", "length": "16650", "offset": "64016172", "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763518115.82/warc/CC-MAIN-20240723194208-20240723224208-00279.warc.gz", "charset": "UTF-8", "languages": "ind,eng"}"#;
        let cdx: Vec<_> = content.lines().map(parse_cdx_line).collect();
        assert_eq!(cdx.len(), 3);
    }

    #[test]
    fn can_parse_cluster_idx_file() {
        let content = r#"0,100,22,165)/ 20240722120756   cdx-00000.gz    0       188224  1
101,141,199,66)/robots.txt 20240714155331       cdx-00000.gz    188224  178351  2
104,223,1,100)/ 20240714230020  cdx-00000.gz    366575  178055  3
107,128,254,23)/sites.asp?domain=hydrogenheaters.com 20240725183414     cdx-00000.gz    544630  181599  4"#;
        let cdx_parts: Vec<_> = content.lines().map(parse_cluster_idx).collect();
        assert_eq!(cdx_parts.len(), 4);
    }
}
