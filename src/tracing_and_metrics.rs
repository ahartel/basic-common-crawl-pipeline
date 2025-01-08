//! This module contains helper methods to set up tracing and a metrics endpoint for Prometheus.
use tracing_subscriber::EnvFilter;

// A small API server that exposes metrics on `/metrics` using `axum`.
pub async fn run_metrics_server(port: u16) {
    async fn metrics() -> String {
        let encoder = prometheus::TextEncoder::new();
        let metrics = prometheus::gather();
        encoder.encode_to_string(&metrics).unwrap()
    }

    let app = axum::Router::new().route("/metrics", axum::routing::get(metrics));
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{port}"))
        .await
        .unwrap();
    tracing::info!("Starting metrics server on port {}", port);
    axum::serve(listener, app.into_make_service())
        .await
        .unwrap()
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
