use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct CdxMetadata {
    pub url: String,
    pub status: String,
    pub length: String,
    pub offset: String,
    pub filename: String,
    pub languages: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CdxEntry {
    pub surt_url: String,
    pub timestamp: String,
    pub metadata: CdxMetadata,
}
