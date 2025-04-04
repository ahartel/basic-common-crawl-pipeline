package main

import (
	"log"

	"github.com/aleph-alpha/case-study/basic-common-crawl-pipeline/golang/worker"
)

func main() {
	if err := worker.Run(); err != nil {
		log.Fatalf("Failed to run worker: %v", err)
	}
}
