use std::io::Read;

use autometrics::autometrics;
use serde::{Deserialize, Serialize};
use serde_aux::prelude::deserialize_number_from_string;

#[derive(Debug, Deserialize, Serialize)]
pub struct CdxMetadata {
    pub url: String,
    #[serde(deserialize_with = "deserialize_number_from_string")]
    pub status: usize,
    #[serde(deserialize_with = "deserialize_number_from_string")]
    pub length: usize,
    #[serde(deserialize_with = "deserialize_number_from_string")]
    pub offset: usize,
    pub filename: String,
    pub languages: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CdxEntry {
    pub surt_url: String,
    pub timestamp: String,
    pub metadata: CdxMetadata,
}

#[autometrics]
pub async fn download_and_unzip(
    url: &str,
    offset: usize,
    length: usize,
) -> Result<Vec<u8>, anyhow::Error> {
    let client = reqwest::Client::new();
    let res = client
        .get(url)
        .header("Range", format!("bytes={}-{}", offset, offset + length - 1))
        .send()
        .await
        .unwrap();
    match res.status() {
        reqwest::StatusCode::PARTIAL_CONTENT => {
            let body = res.bytes().await.unwrap();
            tracing::info!(
                "Successfully fetched the URL {} from {} to {}",
                url,
                offset,
                offset + length - 1
            );
            let mut decoder = flate2::read::GzDecoder::new(&body[..]);
            let mut buffer = Vec::new();
            decoder.read_to_end(&mut buffer).unwrap();
            Ok(buffer)
        }
        _ => Err(anyhow::anyhow!(
            "Failed to fetch index file {}: {}",
            url,
            res.status()
        )),
    }
}
