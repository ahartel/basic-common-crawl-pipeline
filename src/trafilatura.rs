//! This module contains the Python and PyO3 code to be able to use trafilatura
//! from Rust.
use once_cell::sync::Lazy;
use pyo3::{
    types::{PyAnyMethods, PyModule},
    Py, PyAny, PyObject, Python,
};

static PYTHON_SCRIPT: &str = r"
from typing import Optional
from trafilatura import extract

def extract_text(content: str) -> Optional[str]:
    text = extract(content, include_comments=False,
                   include_tables=False, deduplicate=True)
    # also return None if utf-8 decoding failed
    if text is None or isinstance(text, bytes):
        return None
    return text
";

static PYTHON_EXTRACT_FUNCTION: Lazy<Py<PyAny>> = Lazy::new(|| {
    Python::with_gil(move |py| -> PyObject {
        tracing::info!(
            "Loading Python trafilatura with version {:?}.",
            py.version_info()
        );
        let module = PyModule::from_code_bound(py, PYTHON_SCRIPT, "extraction.py", "extraction")
            .expect("Failed to load Python module");
        let extract_function = module
            .getattr("extract_text")
            .expect("Failed to get extract_text function");
        let extract_function = extract_function.into();
        tracing::info!("Loaded Python trafilatura.");
        extract_function
    })
});

/// Extract text from `html` and return the extracted
/// text as string if successful.
/// Might return `Ok(None)` if text extraction was not successful.
pub fn extract(html: &str) -> Result<Option<String>, anyhow::Error> {
    Python::with_gil(move |py| -> Result<Option<String>, anyhow::Error> {
        PYTHON_EXTRACT_FUNCTION
            .call1(py, (html,))?
            .extract(py)
            .map_err(Into::into)
    })
}
