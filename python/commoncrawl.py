import gzip
import requests


def download_and_unzip(url: str, start: int, length: int) -> bytes:
    headers = {"Range": f"bytes={start}-{start+length-1}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    buffer = response.content
    return gzip.decompress(buffer)
