from batcher import process_index
from commoncrawl import Downloader, IndexReader
from rabbitmq import MessageQueueChannel


class FakeReader(IndexReader):
    def __init__(self, data):
        self.data = data

    def __iter__(self):
        return iter(self.data)


class FakeDownloader(Downloader):
    def __init__(self, row: str):
        self.row = row

    def download_and_unzip(self, url: str, start: int, length: int) -> bytes:
        return f"{self.row}".encode("utf-8")


class ChannelSpy(MessageQueueChannel):
    def __init__(self):
        self.num_called = 0

    def basic_publish(self, exchange, routing_key, body):
        self.num_called += 1


def test_filter_non_english_documents():
    reader = FakeReader(
        [
            ["0,100,22,165)/ 20240722120756", "cdx-00000.gz", "0", "188224", "1"],
            [
                "101,141,199,66)/robots.txt 20240714155331",
                "cdx-00000.gz",
                "188224",
                "178351",
                "2",
            ],
            ["104,223,1,100)/ 20240714230020", "cdx-00000.gz", "366575", "178055", "3"],
        ]
    )
    channel = ChannelSpy()
    downloader = FakeDownloader(
        '0,100,22,165)/ 20240722120756 {"url": "http://165.22.100.0/", "mime": "text/html", "mime-detected": "text/html", "status": "301", "digest": "DCNYNIFG5SBRCVS5PCUY4YY2UM2WAQ4R", "length": "689", "offset": "3499", "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/crawldiagnostics/CC-MAIN-20240722095039-20240722125039-00443.warc.gz", "redirect": "https://157.245.55.71/"}\n'
    )
    process_index(reader, channel, downloader, 2)
    assert channel.num_called == 0


def test_filter_bad_status_code():
    reader = FakeReader(
        [
            ["0,100,22,165)/ 20240722120756", "cdx-00000.gz", "0", "188224", "1"],
            [
                "101,141,199,66)/robots.txt 20240714155331",
                "cdx-00000.gz",
                "188224",
                "178351",
                "2",
            ],
            ["104,223,1,100)/ 20240714230020", "cdx-00000.gz", "366575", "178055", "3"],
        ]
    )
    channel = ChannelSpy()
    downloader = FakeDownloader(
        '0,100,22,165)/ 20240722120756 {"url": "http://165.22.100.0/", "mime": "text/html", "mime-detected": "text/html", "status": "301", "languages": "eng", "digest": "DCNYNIFG5SBRCVS5PCUY4YY2UM2WAQ4R", "length": "689", "offset": "3499", "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/crawldiagnostics/CC-MAIN-20240722095039-20240722125039-00443.warc.gz", "redirect": "https://157.245.55.71/"}\n'
    )
    process_index(reader, channel, downloader, 2)
    assert channel.num_called == 0

def test_publish_all_urls():
    reader = FakeReader(
        [
            ["0,100,22,165)/ 20240722120756", "cdx-00000.gz", "0", "188224", "1"],
            [
                "101,141,199,66)/robots.txt 20240714155331",
                "cdx-00000.gz",
                "188224",
                "178351",
                "2",
            ],
            ["104,223,1,100)/ 20240714230020", "cdx-00000.gz", "366575", "178055", "3"],
        ]
    )
    channel = ChannelSpy()
    downloader = FakeDownloader(
        '0,100,22,165)/ 20240722120756 {"url": "http://165.22.100.0/", "mime": "text/html", "mime-detected": "text/html", "status": "200", "languages": "eng", "digest": "DCNYNIFG5SBRCVS5PCUY4YY2UM2WAQ4R", "length": "689", "offset": "3499", "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/crawldiagnostics/CC-MAIN-20240722095039-20240722125039-00443.warc.gz", "redirect": "https://157.245.55.71/"}\n'
        '0,100,22,165)/robots.txt 20240722120755 {"url": "http://165.22.100.0/robots.txt", "mime": "text/html", "mime-detected": "text/html", "status": "200", "languages": "eng", "digest": "LYEE2BXON4MCQCP5FDVDNILOWBKCZZ6G", "length": "700", "offset": "4656", "filename": "crawl-data/CC-MAIN-2024-30/segments/1720763517846.73/robotstxt/CC-MAIN-20240722095039-20240722125039-00410.warc.gz", "redirect": "https://157.245.55.71/robots.txt"}'
    )
    process_index(reader, channel, downloader, 2)
    assert channel.num_called == 3