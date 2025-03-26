package rabbitmq

import (
	"context"
	"encoding/json"
	"fmt"

	amqp "github.com/rabbitmq/amqp091-go"
)

const (
	QueueName = "commoncrawl"
)

type MessageQueueChannel interface {
	Close() error
	BasicPublish(exchange, routingKey string, body []byte) error
	BasicConsume(queue string, handler func(delivery amqp.Delivery)) error
	BasicAck(tag uint64, multiple bool) error
	SetQoS(prefetchCount, prefetchSize int, global bool) error
}

type RabbitMQChannel struct {
	conn    *amqp.Connection
	channel *amqp.Channel
}

func NewRabbitMQChannel() (*RabbitMQChannel, error) {
	conn, err := amqp.Dial("amqp://guest:guest@localhost:32773/")
	if err != nil {
		return nil, fmt.Errorf("failed to connect to RabbitMQ: %w", err)
	}

	ch, err := conn.Channel()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to open channel: %w", err)
	}

	_, err = ch.QueueDeclare(
		QueueName,
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		ch.Close()
		conn.Close()
		return nil, fmt.Errorf("failed to declare queue: %w", err)
	}

	return &RabbitMQChannel{
		conn:    conn,
		channel: ch,
	}, nil
}

func (c *RabbitMQChannel) Close() error {
	if err := c.channel.Close(); err != nil {
		return fmt.Errorf("failed to close channel: %w", err)
	}
	if err := c.conn.Close(); err != nil {
		return fmt.Errorf("failed to close connection: %w", err)
	}
	return nil
}

func (c *RabbitMQChannel) BasicPublish(exchange, routingKey string, body []byte) error {
	return c.channel.PublishWithContext(context.Background(),
		exchange,
		routingKey,
		false,
		false,
		amqp.Publishing{
			ContentType: "application/json",
			Body:        body,
		})
}

func (c *RabbitMQChannel) BasicConsume(queue string, handler func(delivery amqp.Delivery)) error {
	msgs, err := c.channel.Consume(
		queue,
		"",
		false,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		return fmt.Errorf("failed to register a consumer: %w", err)
	}

	go func() {
		for d := range msgs {
			handler(d)
		}
	}()

	return nil
}

func (c *RabbitMQChannel) BasicAck(tag uint64, multiple bool) error {
	return c.channel.Ack(tag, multiple)
}

func (c *RabbitMQChannel) SetQoS(prefetchCount, prefetchSize int, global bool) error {
	return c.channel.Qos(prefetchCount, prefetchSize, global)
}

func PublishBatch(ch MessageQueueChannel, batch interface{}) error {
	body, err := json.Marshal(batch)
	if err != nil {
		return fmt.Errorf("failed to marshal batch: %w", err)
	}

	return ch.BasicPublish("", QueueName, body)
}
