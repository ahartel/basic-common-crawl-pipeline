import pandas as pd
import uuid
import time
import os
from minio_uploader import MinioUploader

SOURCE_DIR = "./tmp/"
BUFFER_SIZE = 20

class ParquetBuffer:
    def __init__(self):
        self.buffer = []
        self.buffer_size = BUFFER_SIZE
        self.minio_uploader = MinioUploader()
    
    def add_record(self, record):
        self.buffer.append(record)
        print(f"Buffer size: {len(self.buffer)}")
        if len(self.buffer) >= self.buffer_size:
            self.flush()
    
    def flush(self):
        if self.buffer:
            df = pd.DataFrame(self.buffer)
            filename = f"batch_{time.time()}_{uuid.uuid4()}.parquet"
            df.to_parquet(SOURCE_DIR + filename)
            self.minio_uploader.upload_to_minio(SOURCE_DIR + filename, filename)
            self.buffer = []
  