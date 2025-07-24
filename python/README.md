# Overview

### Steps to run the project
1. latest version of trafilatura didn't have lxml clean so had to `pip install lxml_html_clean`
2. Setup minio using docker:
    1. Create a local directory for volume: `mkdir -p ${HOME}/minio/data`
    2. ```docker run \
        -p 9090:9000 \
        -p 9091:9091 \
        --user $(id -u):$(id -g) \
        --name minio1 \
        -e "MINIO_ROOT_USER=root" \
        -e "MINIO_ROOT_PASSWORD=password" \
        -v ${HOME}/minio/data:/data \
        quay.io/minio/minio server /data --console-address ":9091"```