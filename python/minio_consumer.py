import os

from abc import ABC, abstractmethod
from typing import Any, Dict
from io import BytesIO
from minio import Minio
from minio.error import S3Error


class Storage(ABC):
    @abstractmethod
    def store(self, parameters: Dict[str, Any], data: str) -> None:
        """Store text data using the provided parameters."""
        pass


MINIO_URL = str(os.getenv("MINIO_CONNECTION_STRING"))
MINIO_ACCESS_KEY = str(os.getenv("MINIO_ACCESS_KEY"))
MINIO_SECRET_KEY = str(os.getenv("MINIO_SECRET_KEY"))


class MinioStorage(Storage):
    def __init__(
        self, endpoint: str, access_key: str, secret_key: str, secure: bool = False
    ):
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def store(self, parameters: Dict[str, Any], data: str) -> None:
        """Store the given string in a MinIO bucket."""
        bucket_name = parameters.get("bucket")
        object_name = parameters.get("object_name")

        if not bucket_name or not object_name:
            raise ValueError(
                "Both 'bucket' and 'object_name' must be provided in parameters."
            )

        # Convert string to bytes
        data_bytes = data.encode("utf-8")
        data_stream = BytesIO(data_bytes)

        # Create bucket if it doesn't exist
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)

        try:
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data_stream,
                length=len(data_bytes),
                content_type=parameters.get(
                    "content_type", "text/plain; charset=utf-8"
                ),
            )
            print(f"Stored object '{object_name}' in bucket '{bucket_name}'.")
        except S3Error as e:
            print(f"Error storing object: {e}")
            raise
