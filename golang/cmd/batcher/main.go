package main

import (
	"log"

	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/batcher"
)

func main() {
	if err := batcher.Main(); err != nil {
		log.Fatalf("Failed to run batcher: %v", err)
	}
}
