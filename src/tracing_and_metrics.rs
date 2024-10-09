use autometrics::prometheus_exporter::{self, PrometheusResponse};
use tracing_subscriber::EnvFilter;

pub async fn run_metrics_server(port: u16) {
    prometheus_exporter::init();

    async fn metrics() -> PrometheusResponse {
        prometheus_exporter::encode_http_response()
    }

    let app = axum::Router::new().route("/metrics", axum::routing::get(metrics));
    let listener = tokio::net::TcpListener::bind(format!("127.0.0.1:{port}"))
        .await
        .unwrap();
    axum::serve(listener, app).await.unwrap();
}

pub fn setup_tracing() {
    // construct a subscriber that prints formatted traces to stdout
    let filter = EnvFilter::from_default_env();
    let subscriber = tracing_subscriber::fmt().with_env_filter(filter).finish();
    // use that subscriber to process traces emitted after this point
    tracing::subscriber::set_global_default(subscriber).unwrap();
    tracing::info!("Tracing initialized");
}
