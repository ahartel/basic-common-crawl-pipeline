use std::io::Read;

#[tokio::main]
async fn main() {
    let client = reqwest::Client::new();
    let res = client
        .get("https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-30/cc-index.paths.gz")
        .send()
        .await
        .unwrap();
    match res.status() {
        reqwest::StatusCode::OK => {
            let body = res.bytes().await.unwrap();
            let mut decoder = flate2::read::GzDecoder::new(&body[..]);
            let mut buffer = Vec::new();
            decoder.read_to_end(&mut buffer).unwrap();
            let paths = String::from_utf8(buffer).unwrap();
            let paths = paths.lines();
            for path in paths {
                println!("{}", path);
            }
        }
        _ => {
            println!("Failed to fetch the index file");
        }
    }
}
