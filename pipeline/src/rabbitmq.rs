use std::time::Duration;

use anyhow::Context;
use lapin::{
    options::{BasicConsumeOptions, BasicQosOptions, QueueDeclareOptions},
    types::FieldTable,
    Channel, Connection, ConnectionProperties, Queue,
};

pub const BATCH_SIZE: usize = 1000;
pub const CC_QUEUE_NAME: &str = "batches";
const RABBIT_MQ_TIMEOUT: Duration = Duration::from_secs(20);

pub fn get_rabbitmq_connection_string() -> String {
    std::env::var("RABBITMQ_CONNECTION_STRING").expect("RABBITMQ_CONNECTION_STRING must be set.")
}

#[tracing::instrument]
pub async fn rabbitmq_connection() -> Result<Connection, anyhow::Error> {
    let connection_string = get_rabbitmq_connection_string();
    let connection = tokio::time::timeout(
        RABBIT_MQ_TIMEOUT,
        Connection::connect(&connection_string, ConnectionProperties::default()),
    )
    .await
    .context("Timed out while trying to connect to RabbitMQ")??;
    Ok(connection)
}

#[tracing::instrument]
pub async fn rabbitmq_channel_with_queue(
    conn: &Connection,
    queue_name: &str,
) -> Result<(Channel, Queue), anyhow::Error> {
    let channel = rabbitmq_channel(conn).await?;
    let queue = rabbitmq_declare_queue(&channel, queue_name, FieldTable::default()).await?;
    Ok((channel, queue))
}

pub async fn rabbitmq_declare_queue(
    channel: &Channel,
    queue_name: &str,
    arguments: FieldTable,
) -> Result<Queue, anyhow::Error> {
    let queue = tokio::time::timeout(
        RABBIT_MQ_TIMEOUT,
        channel.queue_declare(queue_name, QueueDeclareOptions::default(), arguments),
    )
    .await
    .context("Timed out while trying to declare a RabbitMQ queue")?
    .context("Failed to declare RabbitMQ queue")?;

    Ok(queue)
}

pub async fn rabbitmq_channel(conn: &Connection) -> Result<Channel, anyhow::Error> {
    let channel = tokio::time::timeout(RABBIT_MQ_TIMEOUT, conn.create_channel())
        .await
        .context("Timed out while trying to create a RabbitMQ channel")?
        .context("Failed to create RabbitMQ channel")?;

    tokio::time::timeout(
        RABBIT_MQ_TIMEOUT,
        channel.basic_qos(1, BasicQosOptions::default()),
    )
    .await
    .context("Timed out while trying to set QoS on the channel")?
    .context("Failed to set QoS on the channel")?;
    Ok(channel)
}

pub async fn rabbitmq_consumer(
    channel: &Channel,
    queue_name: &str,
    consumer_tag: &str,
) -> Result<lapin::Consumer, anyhow::Error> {
    let consumer = tokio::time::timeout(
        RABBIT_MQ_TIMEOUT,
        channel.basic_consume(
            queue_name,
            consumer_tag,
            BasicConsumeOptions::default(),
            FieldTable::default(),
        ),
    )
    .await
    .context("Timed out while trying to consume from a RabbitMQ queue")??;

    Ok(consumer)
}
