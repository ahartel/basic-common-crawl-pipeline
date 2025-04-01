package batcher

import (
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/common"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/commoncrawl"
	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/rabbitmq"
)

const (
	batchSize = 50
)

var (
	batchCounter = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "batcher_batches",
		Help: "Number of published batches",
	})
)

func init() {
	prometheus.MustRegister(batchCounter)
}

func ProcessIndex(filename string, mq rabbitmq.MessageQueueChannel, downloader commoncrawl.Downloader) error {
	file, err := os.Open(filename)
	if err != nil {
		return fmt.Errorf("failed to open index file: %v", err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	reader.Comma = '\t'         // Use tab as delimiter
	reader.FieldsPerRecord = -1 // Allow variable number of fields

	var foundURLs []common.URL
	count := 0

	for {
		record, err := reader.Read()
		if err != nil {
			if err.Error() == "EOF" {
				break
			}
			log.Printf("Error reading record: %v", err)
			continue
		}

		count++

		if len(record) < 4 {
			log.Printf("Invalid record length: %v", record)
			continue
		}

		startOffset, err := strconv.Atoi(record[2])
		if err != nil {
			log.Printf("Failed to parse start offset: %v", err)
			continue
		}

		length, err := strconv.Atoi(record[3])
		if err != nil {
			log.Printf("Failed to parse length: %v", err)
			continue
		}

		cdxPath := fmt.Sprintf("%s/%s", commoncrawl.CrawlPath, record[1])
		content, err := downloader.DownloadAndUnzip(cdxPath, startOffset, length)
		if err != nil {
			log.Printf("Failed to download and unzip: %v", err)
			continue
		}

		// Parse the downloaded content into URLs
		lines := strings.Split(string(content), "\n")
		for _, line := range lines {
			if line == "" {
				continue
			}

			parts := strings.SplitN(line, " ", 3)
			if len(parts) != 3 {
				continue
			}

			var metadata map[string]interface{}
			if err := json.Unmarshal([]byte(parts[2]), &metadata); err != nil {
				continue
			}

			url := common.URL{
				SurtURL:   parts[0],
				Timestamp: parts[1],
				Metadata:  metadata,
			}

			if languages, ok := url.Metadata["languages"].(string); ok {
				hasEnglish := false
				// Split the comma-separated string into individual languages
				langList := strings.Split(languages, ",")
				for _, lang := range langList {
					if strings.TrimSpace(lang) == "eng" {
						hasEnglish = true
						break
					}
				}

				if !hasEnglish {
					continue
				}
			} else {
				continue
			}

			if status, ok := url.Metadata["status"].(string); !ok || status != "200" {
				continue
			}

			foundURLs = append(foundURLs, url)

			if len(foundURLs) >= batchSize {
				if err := publishBatch(mq, foundURLs); err != nil {
					log.Printf("Failed to publish batch: %v", err)
				}
				foundURLs = nil
			}
		}
	}

	if len(foundURLs) > 0 {
		if err := publishBatch(mq, foundURLs); err != nil {
			log.Printf("Failed to publish batch: %v", err)
		}
	}

	return nil
}

func publishBatch(channel rabbitmq.MessageQueueChannel, batch []common.URL) error {
	log.Printf("Pushing batch of size %d", len(batch))
	if err := rabbitmq.PublishBatch(channel, batch); err != nil {
		return err
	}
	batchCounter.Inc()
	return nil
}

func Run() error {
	clusterIdxFilename := flag.String("cluster-idx-filename", "", "Path to the cluster index file")
	flag.Parse()

	if *clusterIdxFilename == "" {
		return fmt.Errorf("cluster-idx-filename is required")
	}

	go func() {
		http.Handle("/metrics", promhttp.Handler())
		if err := http.ListenAndServe(":9000", nil); err != nil {
			log.Printf("Failed to start metrics server: %v", err)
		}
	}()

	channel, err := rabbitmq.NewRabbitMQChannel()
	if err != nil {
		return fmt.Errorf("failed to create channel: %w", err)
	}
	defer channel.Close()

	downloader := commoncrawl.NewCCDownloader(commoncrawl.BaseURL)

	return ProcessIndex(*clusterIdxFilename, channel, downloader)
}
