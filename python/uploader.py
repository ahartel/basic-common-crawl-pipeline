from abc import ABC, abstractmethod
import io

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from storage import StorageBackend


class AbstractUploader(ABC):
    def __init__(self, storage_backend: StorageBackend):
        self.storage_backend = storage_backend

    @abstractmethod
    def upload(self, object_name: str, data: any, content_type: str):
        pass


class ParquetUploader(AbstractUploader):
    def upload(self, object_name: str, data: any, content_type: str = "application/octet-stream"):
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        df.to_parquet(buffer, engine="pyarrow")
        buffer.seek(0)
        self.storage_backend.upload(object_name, buffer.getvalue(), content_type)