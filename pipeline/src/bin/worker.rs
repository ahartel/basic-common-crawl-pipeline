use futures_util::StreamExt;
use lapin::options::BasicAckOptions;
use pipeline::{
    cdx::{download_and_unzip, CdxEntry},
    rabbitmq::{
        rabbitmq_channel_with_queue, rabbitmq_connection, rabbitmq_consumer, CC_QUEUE_NAME,
    },
    tracing_and_metrics::{run_metrics_server, setup_tracing},
};
use warc::WarcHeader;

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
                tracing::info!(
                    "Received a batch of {} entries",
                    batch.as_ref().unwrap().len()
                );
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
                        tracing::info!(
                            "Successfully read WARC entry with URL {}",
                            warc_entry.header(WarcHeader::TargetURI).unwrap()
                        );
                    }
                }
                delivery.ack(BasicAckOptions::default()).await.unwrap();
            }
            Err(e) => {
                tracing::warn!(err.msg = %e, err.details = ?e, "Failed to receive message from RabbitMQ. Reconnecting.");
                continue;
            }
        }
    }
}
