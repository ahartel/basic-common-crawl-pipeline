//! This module contains helper methods to set up tracing and a metrics endpoint for Prometheus.
use autometrics::prometheus_exporter::{self, PrometheusResponse};
use tracing_subscriber::EnvFilter;

/// Starts a metrics server listening on `port` using the `axum` crate
/// so that Prometheus can scrape the `/metrics` endpoint.
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

/// Constructs a tracing subscriber that prints formatted traces to stdout.
/// Default level is `info` but can be configured via the `RUST_LOG` environment variable.
/// Registers that subscriber to process traces emitted after this point.
pub fn setup_tracing() {
    let filter = EnvFilter::from_default_env();
    let subscriber = tracing_subscriber::fmt().with_env_filter(filter).finish();
    tracing::subscriber::set_global_default(subscriber).unwrap();
    tracing::info!("Tracing initialized");
}
