#!/bin/sh

## a very dumb file to make stuff running
docker start rabbitmq || docker run -d -P -p 5672:5672 -p 15672:15672 --name rabbitmq rabbitmq:management
export RABBITMQ_CONNECTION_STRING=amqp://localhost:5672
export PYTHONPATH=venv/lib/python3.13/site-packages
am start http://localhost:9000 http://localhost:9001 &>/dev/null
