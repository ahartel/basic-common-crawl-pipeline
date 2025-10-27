"""
MinIO client for storing extracted data
"""
import boto3
import os
from botocore.config import Config
from typing import Optional


def get_minio_client():
    """Create and return a MinIO client configured from environment variables"""
    endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9002")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    bucket_name = os.getenv("BUCKET_NAME", "extracteddata")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version='s3v4',
            connect_timeout=60,
            read_timeout=60,
            retries={'max_attempts': 3}
        )
    )
    
    # Create bucket if it doesn't exist
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except:
        s3_client.create_bucket(Bucket=bucket_name)
    
    return s3_client, bucket_name


def upload_to_minio(client, bucket_name: str, key: str, data: str) -> bool:
    """Upload data to MinIO bucket"""
    try:
        client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=data.encode('utf-8'),
            ContentType='text/plain'
        )
        return True
    except Exception as e:
        print(f"Failed to upload to MinIO: {e}")
        return False

