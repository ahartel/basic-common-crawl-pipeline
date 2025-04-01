package worker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"

	"github.com/PuerkitoBio/goquery"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	amqp "github.com/rabbitmq/amqp091-go"
	"github.com/slyrz/warc"

	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/common"
	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/commoncrawl"
	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/rabbitmq"
)

var (
	batchCounter = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "worker_batches",
		Help: "Number of consumed batches",
	})
)

func init() {
	prometheus.MustRegister(batchCounter)
}

// extractText extracts text content from HTML using goquery
func extractText(htmlContent []byte) string {
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(htmlContent))
	if err != nil {
		log.Printf("Failed to parse HTML: %v", err)
		return ""
	}

	doc.Find("script, style").Each(func(i int, s *goquery.Selection) {
		s.Remove()
	})

	text := doc.Text()
	text = strings.Join(strings.Fields(text), " ")

	return text
}

func ProcessBatch(downloader commoncrawl.Downloader, delivery amqp.Delivery) error {
	var batch []common.URL
	if err := json.Unmarshal(delivery.Body, &batch); err != nil {
		return fmt.Errorf("failed to unmarshal batch: %w", err)
	}

	for _, item := range batch {
		offset, err := strconv.Atoi(item.Metadata["offset"].(string))
		if err != nil {
			return fmt.Errorf("failed to parse offset: %w", err)
		}

		length, err := strconv.Atoi(item.Metadata["length"].(string))
		if err != nil {
			return fmt.Errorf("failed to parse length: %w", err)
		}

		data, err := downloader.DownloadAndUnzip(
			item.Metadata["filename"].(string),
			offset,
			length,
		)
		if err != nil {
			return fmt.Errorf("failed to download and unzip: %w", err)
		}

		reader, err := warc.NewReader(bytes.NewReader(data))
		if err != nil {
			return fmt.Errorf("failed to create WARC reader: %w", err)
		}
		defer reader.Close()

		for {
			record, err := reader.ReadRecord()
			if err != nil {
				if err == io.EOF {
					break
				}

				return fmt.Errorf("failed to read WARC record: %w", err)
			}
			if record.Header.Get("WARC-Type") != "response" {
				continue
			}

			content, err := io.ReadAll(record.Content)
			if err != nil {
				return fmt.Errorf("failed to read WARC record content: %w", err)
			}

			// Find the start of HTML content (after headers)
			htmlStart := bytes.Index(content, []byte("\r\n\r\n"))
			if htmlStart == -1 {
				htmlStart = bytes.Index(content, []byte("\n\n"))
			}
			if htmlStart == -1 {
				log.Printf("Could not find HTML content start for URL %s", item.SurtURL)
				continue
			}

			text := extractText(content[htmlStart+4:])
			if text != "" {
				log.Printf("Text: %s", text)
				// TODO: Process the extracted text (e.g., save to file, send to another service)
			}
		}
	}

	batchCounter.Inc()
	return nil
}

func Run() error {
	go func() {
		http.Handle("/metrics", promhttp.Handler())
		if err := http.ListenAndServe(":9001", nil); err != nil {
			log.Printf("Failed to start metrics server: %v", err)
		}
	}()

	downloader := commoncrawl.NewCCDownloader(commoncrawl.BaseURL)

	channel, err := rabbitmq.NewRabbitMQChannel()
	if err != nil {
		return fmt.Errorf("failed to create RabbitMQ channel: %w", err)
	}
	defer channel.Close()

	if err := channel.SetQoS(1, 0, false); err != nil {
		return fmt.Errorf("failed to set QoS: %w", err)
	}

	if err := channel.BasicConsume(rabbitmq.QueueName, func(delivery amqp.Delivery) {
		if err := ProcessBatch(downloader, delivery); err != nil {
			log.Printf("Failed to process batch: %v", err)
			return
		}
		if err := channel.BasicAck(delivery.DeliveryTag, false); err != nil {
			log.Printf("Failed to acknowledge message: %v", err)
		}
	}); err != nil {
		return fmt.Errorf("failed to start consuming: %w", err)
	}

	log.Printf("Started consuming")

	select {}
}
