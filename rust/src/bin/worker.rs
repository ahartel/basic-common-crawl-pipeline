//! The worker(s) pull(s) messages from the RabbitMQ queue and downloads the WARC files that contain the actual content of the URLs.
//! Once the content has been downloaded, the worker extracts the text from the HTML file using the trafilatura Python package.
//!
//! After having downloaded and extracted the text from the HTML file, the worker could apply some filters to the extracted text.
//! We would also want to tokenize (for LLM training) the text and output it to a file.
//!
//! In its current implementation it does not refine or filter the extracted text in any way nor does it output the extracted text to a file.
use futures_util::StreamExt;
use lapin::options::BasicAckOptions;
use lazy_static::lazy_static;
use prometheus::{register_int_counter, IntCounter};
use pipeline::{
    commoncrawl::{download_and_unzip, CdxEntry},
    rabbitmq::{
        rabbitmq_channel_with_queue, rabbitmq_connection, rabbitmq_consumer, CC_QUEUE_NAME,
    },
    tracing_and_metrics::{run_metrics_server, setup_tracing},
    trafilatura,
};
use warc::WarcHeader;

lazy_static! {
    static ref RABBITMQ_CONNECTION_ERRORS_COUNTER: IntCounter = register_int_counter!(
        "crawler_worker_rabbitmq_connection_errors",
        "Number of RabbitMQ connection errors."
    )
    .unwrap();

    // Batch metrics
    static ref BATCHES_RECEIVED_COUNTER: IntCounter = register_int_counter!(
        "crawler_worker_batches_received",
        "Number of batches received by the worker."
    )
    .unwrap();

    // Entry metrics
    static ref ENTRIES_RECEIVED_COUNTER: IntCounter = register_int_counter!(
        "crawler_worker_entries_received",
        "Number of entries received inside batches by the worker."
    )
    .unwrap();

    // WARC Entry metrics
    static ref WARC_ENTRIES_PARSED_COUNTER: IntCounter = register_int_counter!(
        "crawler_worker_warc_parsed",
        "Number of WARC entries parsed from events by the worker."
    )
    .unwrap();

    static ref WARC_ENTRIES_EXTRACTED_COUNTER: IntCounter = register_int_counter!(
        "crawler_worker_warc_extracted",
        "Number of WARC entries extracted by the worker."
    )
    .unwrap();

    static ref WARC_ENTRIES_EXTRACTION_ERRORS_COUNTER: IntCounter = register_int_counter!(
        "crawler_worker_warc_extraction_errors",
        "Number of WARC entry extraction errors by the worker."
    )
    .unwrap();

}

#[tokio::main]
async fn main() {
    setup_tracing();
    tokio::task::spawn(run_metrics_server(9001));

    let rabbit_conn = rabbitmq_connection().await.unwrap();
    let (channel, _queue) = rabbitmq_channel_with_queue(&rabbit_conn, CC_QUEUE_NAME)
        .await
        .unwrap();
    let mut consumer = rabbitmq_consumer(&channel, CC_QUEUE_NAME, "worker")
        .await
        .unwrap();
    while let Some(delivery) = consumer.next().await {
        match delivery {
            Ok(delivery) => {
                let batch = serde_json::from_slice::<Vec<CdxEntry>>(&delivery.data);
                BATCHES_RECEIVED_COUNTER.inc();
                let batch_size = batch.as_ref().unwrap().len();
                tracing::info!(
                    "Received a batch of {} entries",
                    batch_size
                );
                ENTRIES_RECEIVED_COUNTER.inc_by(batch_size as u64);
                for entry in batch.unwrap() {
                    let data = download_and_unzip(
                        &format!("https://data.commoncrawl.org/{}", entry.metadata.filename),
                        entry.metadata.offset,
                        entry.metadata.length,
                    )
                    .await
                    .unwrap();
                    for warc_entry in warc::WarcReader::new(data.as_slice()).iter_records() {
                        let warc_entry = warc_entry.unwrap();
                        if warc_entry.header(WarcHeader::WarcType).unwrap() != "response" {
                            continue;
                        }
                        tracing::info!(
                            "Successfully read WARC entry with URL {}",
                            warc_entry.header(WarcHeader::TargetURI).unwrap()
                        );
                        let raw_content = String::from_utf8_lossy(warc_entry.body());
                        let html_begin_index = raw_content.find("\n\n");
                        let Some(html_begin_index) = html_begin_index else {
                            tracing::warn!("Failed to find HTML content in WARC entry");
                            continue;
                        };
                        WARC_ENTRIES_PARSED_COUNTER.inc();

                        tracing::debug!(
                            "First 2000 characters of raw content: {}",
                            &raw_content[..2000]
                        );
                        let content =
                            trafilatura::extract(&raw_content[html_begin_index..]).unwrap();
                        if let Some(content) = content {
                            tracing::info!("Extracted content of length {}", content.len());
                            tracing::debug!("Extracted content: {}", &content);
                            WARC_ENTRIES_EXTRACTED_COUNTER.inc();
                        } else {
                            tracing::warn!("Failed to extract content from WARC entry");
                            WARC_ENTRIES_EXTRACTION_ERRORS_COUNTER.inc();
                        }
                    }
                }
                delivery.ack(BasicAckOptions::default()).await.unwrap();
            }
            Err(e) => {
                tracing::warn!(err.msg = %e, err.details = ?e, "Failed to receive message from RabbitMQ. Reconnecting.");
                RABBITMQ_CONNECTION_ERRORS_COUNTER.inc();
                continue;
            }
        }
    }
}
