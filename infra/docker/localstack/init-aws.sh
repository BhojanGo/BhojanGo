#!/bin/bash
set -e

echo "Initializing LocalStack AWS resources..."

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1"

# ── DLQ Queues ──────────────────────────────
$AWS_CMD sqs create-queue --queue-name bhojango-order-events-dlq
$AWS_CMD sqs create-queue --queue-name bhojango-payment-events-dlq
$AWS_CMD sqs create-queue --queue-name bhojango-notification-events-dlq
$AWS_CMD sqs create-queue --queue-name bhojango-delivery-events-dlq

# ── Main SQS Queues (with DLQ redrive) ─────
ORDER_DLQ_ARN=$($AWS_CMD sqs get-queue-attributes \
  --queue-url http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/bhojango-order-events-dlq \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

PAYMENT_DLQ_ARN=$($AWS_CMD sqs get-queue-attributes \
  --queue-url http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/bhojango-payment-events-dlq \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

NOTIFICATION_DLQ_ARN=$($AWS_CMD sqs get-queue-attributes \
  --queue-url http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/bhojango-notification-events-dlq \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

DELIVERY_DLQ_ARN=$($AWS_CMD sqs get-queue-attributes \
  --queue-url http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/bhojango-delivery-events-dlq \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

$AWS_CMD sqs create-queue --queue-name bhojango-order-events \
  --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$ORDER_DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"

$AWS_CMD sqs create-queue --queue-name bhojango-payment-events \
  --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$PAYMENT_DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"

$AWS_CMD sqs create-queue --queue-name bhojango-notification-events \
  --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$NOTIFICATION_DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"

$AWS_CMD sqs create-queue --queue-name bhojango-delivery-events \
  --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DELIVERY_DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"

# ── SNS Topics ──────────────────────────────
$AWS_CMD sns create-topic --name bhojango-order-topic
$AWS_CMD sns create-topic --name bhojango-payment-topic
$AWS_CMD sns create-topic --name bhojango-driver-topic
$AWS_CMD sns create-topic --name bhojango-notification-topic
$AWS_CMD sns create-topic --name bhojango-user-topic

# ── Subscribe SQS to SNS ───────────────────
ORDER_QUEUE_ARN=$($AWS_CMD sqs get-queue-attributes \
  --queue-url http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/bhojango-order-events \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

NOTIFICATION_QUEUE_ARN=$($AWS_CMD sqs get-queue-attributes \
  --queue-url http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/bhojango-notification-events \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

ORDER_TOPIC_ARN=$($AWS_CMD sns list-topics \
  --query 'Topics[?contains(TopicArn, `bhojango-order-topic`)].TopicArn' --output text)

PAYMENT_TOPIC_ARN=$($AWS_CMD sns list-topics \
  --query 'Topics[?contains(TopicArn, `bhojango-payment-topic`)].TopicArn' --output text)

# Notification queue subscribes to order and payment events
$AWS_CMD sns subscribe --topic-arn "$ORDER_TOPIC_ARN" --protocol sqs --notification-endpoint "$NOTIFICATION_QUEUE_ARN"
$AWS_CMD sns subscribe --topic-arn "$PAYMENT_TOPIC_ARN" --protocol sqs --notification-endpoint "$NOTIFICATION_QUEUE_ARN"

# ── S3 Buckets ──────────────────────────────
$AWS_CMD s3 mb s3://bhojango-uploads 2>/dev/null || true
$AWS_CMD s3 mb s3://bhojango-assets 2>/dev/null || true

echo "LocalStack initialization complete!"
echo "Queues:"
$AWS_CMD sqs list-queues
echo "Topics:"
$AWS_CMD sns list-topics
