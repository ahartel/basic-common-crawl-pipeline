package commoncrawl

import (
	"bytes"
	"compress/gzip"
	"fmt"
	"io"
	"log"
	"net/http"
)

const (
	BaseURL   = "https://data.commoncrawl.org"
	CrawlPath = "cc-index/collections/CC-MAIN-2024-30/indexes"
)

type Downloader interface {
	DownloadAndUnzip(url string, start, length int) ([]byte, error)
}

type CCDownloader struct {
	baseURL string
}

func NewCCDownloader(baseURL string) *CCDownloader {
	return &CCDownloader{baseURL: baseURL}
}

func (d *CCDownloader) DownloadAndUnzip(url string, start, length int) ([]byte, error) {
	fullURL := fmt.Sprintf("%s/%s", BaseURL, url)

	client := &http.Client{}
	req, err := http.NewRequest("GET", fullURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Range", fmt.Sprintf("bytes=%d-%d", start, start+length-1))
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to download: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusPartialContent && resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("Failed to read response body: %v", err)
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	reader, err := gzip.NewReader(bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create gzip reader: %w", err)
	}
	defer reader.Close()

	content, err := io.ReadAll(reader)
	if err != nil {
		return nil, fmt.Errorf("failed to read gzipped content: %w", err)
	}

	return content, nil
}
