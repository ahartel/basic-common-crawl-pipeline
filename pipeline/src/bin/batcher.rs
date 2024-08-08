use std::io::Read;

async fn download_and_unzip(url: &str) -> Result<Vec<String>, anyhow::Error> {
    let client = reqwest::Client::new();
    let res = client.get(url).send().await.unwrap();
    match res.status() {
        reqwest::StatusCode::OK => {
            let body = res.bytes().await.unwrap();
            let mut decoder = flate2::read::GzDecoder::new(&body[..]);
            let mut buffer = Vec::new();
            decoder.read_to_end(&mut buffer).unwrap();
            let paths = String::from_utf8(buffer).unwrap();
            Ok(paths.lines().map(|s| s.to_string()).collect())
        }
        _ => {
            println!("Failed to fetch the index file");
            Err(anyhow::anyhow!("Failed to fetch the index file"))
        }
    }
}

#[tokio::main]
async fn main() {
    let paths = download_and_unzip(
        "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-30/cc-index.paths.gz",
    )
    .await
    .unwrap();
    for path in paths {
        println!("{}", path);
    }
}
