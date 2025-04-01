package main

import (
	"log"

	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/batcher"
)

func main() {
	if err := batcher.Run(); err != nil {
		log.Fatalf("Failed to run batcher: %v", err)
	}
}
