use once_cell::sync::Lazy;
use pyo3::{
    types::{PyAnyMethods, PyModule},
    Py, PyAny, PyObject, Python,
};

static PYTHON_SCRIPT: &str = r"
from trafilatura import extract

def extract_text(content: str) -> str:
    text = extract(content, include_comments=False,
                   include_tables=False, deduplicate=True)
    if text is None or isinstance(text, bytes):
        return
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

pub fn extract(html: &str) -> Result<Option<String>, anyhow::Error> {
    Python::with_gil(move |py| -> Result<Option<String>, anyhow::Error> {
        PYTHON_EXTRACT_FUNCTION
            .call1(py, (html,))?
            .extract(py)
            .map_err(Into::into)
    })
}
