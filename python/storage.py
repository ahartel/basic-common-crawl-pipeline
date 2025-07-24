from abc import ABC, abstractmethod
import io

from minio import Minio

class StorageBackend(ABC):
    @abstractmethod
    def upload(self, object_name: str, data: bytes, content_type: str):
        """
        Uploads a file to the storage backend.
        """
        raise NotImplementedError("Subclasses must implement this method")

class MinioStorageBackend(StorageBackend):
    def __init__(self, minio_client, minio_bucket):
        self.minio_client = minio_client
        self.minio_bucket = minio_bucket

    def upload(self, object_name: str, data: bytes, content_type: str):
        buffer = io.BytesIO(data)
        self.minio_client.put_object(
            self.minio_bucket,
            object_name,
            buffer,
            length=buffer.getbuffer().nbytes,
            content_type=content_type
        )

def get_minio_client(endpoint: str, access_key: str, secret_key: str, secure=False):
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)