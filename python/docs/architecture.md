# Architecture Documentation

Complete architectural overview of the Common Crawl Pipeline system.

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Data Flow & File Hierarchy](#data-flow--file-hierarchy)
3. [Component Details](#component-details)
4. [Design Patterns](#design-patterns)
5. [Key Concepts](#key-concepts)
6. [Codebase Structure](#codebase-structure)

---

## High-Level Architecture

### System Overview

```
┌──────────────┐
│ cluster.idx  │ (Downloaded once with wget)
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Batcher    │────▶│  RabbitMQ   │────▶│   Worker(s)  │
│  (Producer)  │     │    Queue    │     │  (Consumers) │
└──────────────┘     └─────────────┘     └──────────────┘
       │                                         │
       │ Downloads chunks from                  │ Downloads chunks from
       ▼                                         ▼
┌──────────────┐                         ┌──────────────┐
│  CDX Files   │                         │  WARC Files  │
│  (Metadata)  │                         │   (Content)  │
└──────────────┘                         └──────────────┘
```

### Components

| Component | Type | Instances | Purpose |
|-----------|------|-----------|---------|
| **Batcher** | Producer | Single | Filters URLs, publishes batches |
| **Worker** | Consumer | Multiple (scalable) | Downloads content, extracts text |
| **RabbitMQ** | Message Queue | Single | Decouples producer/consumer |
| **Prometheus** | Monitoring | Single | Collects metrics from all components |

### Ports

| Service | Port | Purpose |
|---------|------|---------|
| RabbitMQ AMQP | 5672 | Message queue protocol |
| RabbitMQ Management | 15672 | Web UI for monitoring |
| Prometheus | 9090 | Metrics collection and queries |
| Batcher Metrics | 9000 | Prometheus scrape endpoint |
| Worker Metrics | 9001+ | Prometheus scrape endpoint (9001, 9002, ...) |

---

## Data Flow & File Hierarchy

### The Three-Layer File Structure

Common Crawl uses a three-tier hierarchy to enable efficient partial downloads:

```
cluster.idx (1 file, ~118MB - you download this)
    ↓ points to →
CDX index files (hundreds, ~1GB each - batcher downloads chunks)
    ↓ points to →
WARC files (thousands - workers download chunks)
```

### Layer 1: cluster.idx (Local File)

**What it is**: A single "table of contents" file that maps URL ranges to CDX file locations.

**Format**: Tab-separated values (TSV)

```
0,100,22,165)/ 20240722120756   cdx-00000.gz    0       188224  1
101,141,199,66)/robots.txt 20240714155331       cdx-00000.gz    188224  178351  2
104,223,1,100)/ 20240714230020  cdx-00000.gz    366575  178055  3
```

**Columns**:
1. **SURT URL** + timestamp - Identifies URL range
2. **CDX filename** - Which index file contains metadata (e.g., `cdx-00000.gz`)
3. **Offset** - Byte position in the CDX file
4. **Length** - Number of bytes to download
5. **Index** - Line number in cluster.idx

**Purpose**: Enables downloading only relevant portions of massive CDX files instead of entire gigabyte files.

### Layer 2: CDX Index Files (Remote, Chunked Downloads)

**What it is**: Hundreds of compressed files (`cdx-00000.gz`, `cdx-00001.gz`, ...), each ~1GB.

**Contains**: Metadata about crawled URLs (NO actual HTML content).

**Format**: Space-separated with JSON metadata

```
0,100,22,165)/
20240722120756
{
    "url": "http://165.22.100.0/",
    "mime": "text/html",
    "status": "200",
    "languages": "eng",
    "length": "689",
    "offset": "3499",
    "filename": "crawl-data/CC-MAIN-2024-30/.../file.warc.gz"
}
```

**Key Fields**:
- `status`: HTTP status code (batcher filters for "200")
- `languages`: Language code (batcher filters for "eng")
- `filename`: WARC file path containing actual HTML
- `offset`: Byte position in WARC file
- `length`: Number of bytes to download from WARC

**Batcher's Role**:
1. Download chunks using HTTP Range headers
2. Filter by language and status
3. Batch filtered URLs
4. Publish to RabbitMQ

### Layer 3: WARC Files (Remote, Chunked Downloads)

**What it is**: Thousands of Web ARChive files containing actual HTML content.

**Contains**: Multiple web pages compressed together in WARC format.

**Worker's Role**:
1. Download specific byte ranges (single page content)
2. Parse WARC format
3. Extract text using trafilatura
4. Process/filter text (future enhancement)

---

## Component Details

### Batcher (`src/commoncrawl_pipeline/batcher.py`)

**Responsibility**: Read cluster.idx, filter URLs, batch and publish to RabbitMQ.

**Entry Point**: `main()` function

**Process Flow**:

```python
# 1. Start Prometheus metrics server
start_http_server(9000)

# 2. Connect to RabbitMQ
channel = RabbitMQChannel()

# 3. Create downloader for CDX files
downloader = CCDownloader(f"{BASE_URL}/{CRAWL_PATH}")

# 4. Open cluster.idx file
index_reader = CSVIndexReader(args.cluster_idx_filename)

# 5. Process each chunk
for cdx_chunk in index_reader:
    # Download CDX chunk
    data = downloader.download_and_unzip(
        cdx_chunk[1],        # filename
        int(cdx_chunk[2]),   # offset
        int(cdx_chunk[3])    # length
    )

    # Parse and filter URLs
    for line in data.split("\n"):
        metadata = parse_line(line)
        if is_english_and_200(metadata):
            found_urls.append(metadata)

    # Publish batch when full
    if len(found_urls) >= BATCH_SIZE:
        publish_batch(channel, found_urls)
```

**Filtering Logic** (`process_index()` function):
- Language must be English (`"eng" in metadata["languages"]`)
- HTTP status must be 200 (`metadata["status"] == "200"`)

**Configuration**:
- Batch size: `BATCH_SIZE = 50` (hardcoded)
- Metrics port: `9000` (hardcoded)
- Crawl version: `CC-MAIN-2024-30` (hardcoded)

**Metrics**:
- `batcher_batches`: Counter of published batches

### Worker (`src/commoncrawl_pipeline/worker.py`)

**Responsibility**: Consume batches from RabbitMQ, download WARC files, extract text.

**Entry Point**: `main()` function

**Process Flow**:

```python
# 1. Start Prometheus metrics server
start_http_server(9001)

# 2. Create downloader for WARC files
downloader = CCDownloader(BASE_URL)

# 3. Connect to RabbitMQ
channel = rabbitmq_channel()
channel.basic_qos(prefetch_count=1)

# 4. Start consuming messages
channel.basic_consume(
    queue=QUEUE_NAME,
    on_message_callback=process_batch
)
channel.start_consuming()

# 5. Process each batch
def process_batch(body):
    batch = json.loads(body)
    for item in batch:
        # Download WARC chunk
        data = downloader.download_and_unzip(
            item["metadata"]["filename"],
            item["metadata"]["offset"],
            item["metadata"]["length"]
        )

        # Extract text
        for record in WARCIterator(data):
            if record.rec_type == "response":
                text = trafilatura.extract(record.content)
                # TODO: process text

    # Acknowledge message
    ch.basic_ack()
```

**Configuration**:
- Metrics port: `9001` (hardcoded)
- Prefetch count: `1` (hardcoded)

**Metrics**:
- `worker_batches`: Counter of consumed batches

### Common Crawl Module (`src/commoncrawl_pipeline/commoncrawl.py`)

Provides abstractions for downloading and reading Common Crawl data.

**Classes**:

1. **`Downloader` (ABC)**: Interface for downloading data
2. **`CCDownloader`**: Concrete implementation using HTTP Range requests
3. **`IndexReader` (ABC)**: Interface for reading index files
4. **`CSVIndexReader`**: Reads cluster.idx with tab-separated values

**Key Implementation**:

```python
class CCDownloader(Downloader):
    def download_and_unzip(self, url: str, start: int, length: int) -> bytes:
        # HTTP Range request for partial download
        headers = {"Range": f"bytes={start}-{start+length-1}"}
        response = requests.get(f"{self.base_url}/{url}", headers=headers)
        response.raise_for_status()
        # Decompress gzip content
        return gzip.decompress(response.content)
```

**Constants**:
- `BASE_URL = "https://data.commoncrawl.org"`
- `CRAWL_PATH = "cc-index/collections/CC-MAIN-2024-30/indexes"`

### RabbitMQ Module (`src/commoncrawl_pipeline/rabbitmq.py`)

Abstracts RabbitMQ connection and channel management.

**Classes**:

1. **`MessageQueueChannel` (ABC)**: Interface for message publishing
2. **`RabbitMQChannel`**: Concrete implementation

**Key Implementation**:

```python
def rabbitmq_channel():
    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ["RABBITMQ_CONNECTION_STRING"])
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME)
    return channel
```

**Configuration**:
- Queue name: `"batches"` (hardcoded)
- Connection string: From environment variable `RABBITMQ_CONNECTION_STRING`

---

## Design Patterns

### 1. Abstract Base Classes (ABC) Pattern

**Purpose**: Enable dependency injection and testability.

**Example**:

```python
# Define interface
class Downloader(ABC):
    @abstractmethod
    def download_and_unzip(self, url: str, start: int, length: int) -> bytes:
        pass

# Production implementation
class CCDownloader(Downloader):
    def download_and_unzip(self, url: str, start: int, length: int) -> bytes:
        # Real HTTP requests
        ...

# Test implementation
class FakeDownloader(Downloader):
    def download_and_unzip(self, url: str, start: int, length: int) -> bytes:
        # Return canned data
        return b"fake data"
```

**Benefits**:
- Easy testing without mocking libraries
- Type safety with type hints
- Swappable implementations (e.g., S3Downloader, LocalFileDownloader)

**Used in**:
- `Downloader` / `CCDownloader` (commoncrawl.py)
- `IndexReader` / `CSVIndexReader` (commoncrawl.py)
- `MessageQueueChannel` / `RabbitMQChannel` (rabbitmq.py)

### 2. Iterator Pattern

**Purpose**: Stream large files without loading into memory.

**Example**:

```python
class CSVIndexReader(IndexReader):
    def __iter__(self):
        return self

    def __next__(self):
        return next(self.reader)

# Usage
for row in index_reader:
    process(row)  # Memory efficient streaming
```

**Benefits**:
- Low memory footprint for large files
- Clean integration with Python for loops
- Lazy evaluation

### 3. Dependency Injection

**Purpose**: Functions depend on interfaces, not concrete implementations.

**Example**:

```python
def process_index(
    index: IndexReader,          # Not CSVIndexReader
    channel: MessageQueueChannel, # Not RabbitMQChannel
    downloader: Downloader,       # Not CCDownloader
    batch_size: int,
) -> None:
    # Function works with any implementation
    ...
```

**Benefits**:
- Testable without infrastructure dependencies
- Flexible and maintainable
- Follows SOLID principles (Dependency Inversion)

---

## Key Concepts

### SURT URLs

**SURT** = Sort-friendly URI Reordering Transform

Reverses domain components for alphabetical clustering:

| Original | SURT |
|----------|------|
| `http://example.com/page` | `com,example)/page` |
| `http://165.22.100.0/` | `0,100,22,165)/` |
| `https://subdomain.example.com/path` | `com,example,subdomain)/path` |

**Why**: Enables efficient range-based lookups and alphabetical grouping of related domains.

### Byte-Range Downloads (HTTP Range Requests)

Both batcher and worker use partial downloads to avoid fetching entire files:

```python
headers = {"Range": f"bytes={start}-{start+length-1}"}
response = requests.get(url, headers=headers)
```

**Benefits**:
- Download only needed portions (e.g., 200KB instead of 1GB)
- Efficient bandwidth usage
- Faster processing
- Enables parallel processing of different file chunks

**Example**:
```
File: cdx-00000.gz (1GB total)
Request: bytes=188224-366574 (178KB chunk)
Result: Only downloads the requested portion
```

### Prometheus Metrics

**Current Metrics**:
- `batcher_batches`: Total batches published
- `worker_batches`: Total batches consumed

**Endpoints**:
- Batcher: `http://localhost:9000/metrics`
- Worker: `http://localhost:9001/metrics`

**Prometheus Queries**:
```promql
# Batch publishing rate
rate(batcher_batches[5m])

# Total worker throughput
sum(rate(worker_batches[5m]))

# Worker lag (messages in queue)
rabbitmq_queue_messages{queue="batches"}
```

### Message Format

Messages published to RabbitMQ contain arrays of URL metadata:

```json
[
  {
    "surt_url": "0,100,22,165)/",
    "timestamp": "20240722120756",
    "metadata": {
      "url": "http://165.22.100.0/",
      "status": "200",
      "languages": "eng",
      "filename": "crawl-data/.../file.warc.gz",
      "offset": "3499",
      "length": "689"
    }
  },
  // ... up to BATCH_SIZE items
]
```

---

## Codebase Structure

### Package Layout

```
src/commoncrawl_pipeline/
├── __init__.py           # Package initialization
├── batcher.py            # Batcher implementation (91 lines)
├── worker.py             # Worker implementation (48 lines)
├── commoncrawl.py        # Common Crawl utilities (69 lines)
└── rabbitmq.py           # RabbitMQ utilities (35 lines)

tests/
├── __init__.py
└── test_batcher.py       # Batcher tests with fakes (93 lines)
```

### Module Dependencies

```
batcher.py
├── commoncrawl.py (BASE_URL, CRAWL_PATH, CCDownloader, CSVIndexReader)
└── rabbitmq.py (QUEUE_NAME, RabbitMQChannel)

worker.py
├── commoncrawl.py (BASE_URL, CCDownloader)
└── rabbitmq.py (QUEUE_NAME, rabbitmq_channel)

test_batcher.py
├── batcher.py (process_index)
├── commoncrawl.py (Downloader, IndexReader)
└── rabbitmq.py (MessageQueueChannel)
```

### Key Functions

| Function | Module | Purpose | Lines |
|----------|--------|---------|-------|
| `main()` | batcher.py | Entry point for batcher | 80-86 |
| `process_index()` | batcher.py | Main filtering logic | 44-77 |
| `publish_batch()` | batcher.py | Publish to RabbitMQ | 31-41 |
| `main()` | worker.py | Entry point for worker | 32-43 |
| `process_batch()` | worker.py | Download and extract text | 15-29 |
| `rabbitmq_channel()` | rabbitmq.py | Create RabbitMQ connection | 27-34 |

### Test Architecture

Uses fake implementations instead of mocks:

```python
class FakeReader(IndexReader):
    """Returns hardcoded test data"""

class FakeDownloader(Downloader):
    """Returns canned responses"""

class ChannelSpy(MessageQueueChannel):
    """Counts publish() calls"""
```

**Test Cases**:
- `test_filter_non_english_documents`: Verifies language filtering
- `test_filter_bad_status_code`: Verifies HTTP status filtering
- `test_publish_all_urls`: Verifies batch publishing logic

---

## Scaling Considerations

### Why Single Batcher?

- Processes cluster.idx sequentially (single file)
- Publishing to queue is fast (non-blocking)
- Network download is the bottleneck, not CPU

### Why Multiple Workers?

- Stateless processing (no shared state)
- Download-heavy (benefits from parallelization)
- RabbitMQ handles load balancing automatically

### Bottlenecks

1. **Network bandwidth**: Downloading WARC files
2. **RabbitMQ throughput**: Message queue capacity
3. **Trafilatura processing**: Text extraction CPU usage

### Potential Optimizations

- Use async/await for concurrent downloads
- Batch database writes
- Add worker-side caching
- Implement circuit breakers for failed downloads

---

## Error Handling Gaps

The current implementation deliberately omits error handling for educational purposes:

1. **No retry logic** for failed HTTP requests
2. **No handling** of malformed CDX/WARC entries
3. **No recovery** from RabbitMQ connection loss
4. **No validation** of JSON metadata
5. **No timeout** configuration for downloads

These would be addressed in a production system.
