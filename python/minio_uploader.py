# file_uploader.py MinIO Python SDK example
from minio import Minio
from minio.error import S3Error
import os   
BUCKET_NAME = "crawlobjects"
ENDPOINT= "localhost:9002"
ACCESS_KEY = "minioadmin"
SECRET_KEY = "minioadmin"


class MinioUploader:
    def __init__(self):
        self.client = Minio(
            endpoint=ENDPOINT,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            secure=False
        )


    def upload_to_minio(self, source_file, destination_file):
        
        found = self.client.bucket_exists(bucket_name=BUCKET_NAME)
        if not found:
            self.client.make_bucket(bucket_name=BUCKET_NAME)
            print("Created bucket", BUCKET_NAME)
        else:
            print("Bucket", BUCKET_NAME, "already exists")

        self.client.fput_object(
            bucket_name=BUCKET_NAME,
            object_name=destination_file,
            file_path=source_file,
        )
        print(
            source_file, "successfully uploaded as object",
            destination_file, "to bucket", BUCKET_NAME,
        )
        os.remove(source_file)
