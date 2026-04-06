#!/bin/bash
set -e

echo "Initializing LocalStack AWS resources..."

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1"

# SQS Queues
$AWS_CMD sqs create-queue --queue-name bhojango-notifications
$AWS_CMD sqs create-queue --queue-name bhojango-notifications-dlq
$AWS_CMD sqs create-queue --queue-name bhojango-order-events

# SNS Topics
$AWS_CMD sns create-topic --name bhojango-order-events
$AWS_CMD sns create-topic --name bhojango-payment-events

# S3 Buckets
$AWS_CMD s3 mb s3://bhojango-uploads
$AWS_CMD s3 mb s3://bhojango-assets

# Subscribe SQS to SNS
NOTIFICATION_QUEUE_ARN=$($AWS_CMD sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/bhojango-notifications \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

ORDER_EVENTS_TOPIC_ARN=$($AWS_CMD sns list-topics \
  --query 'Topics[?contains(TopicArn, `bhojango-order-events`)].TopicArn' \
  --output text)

$AWS_CMD sns subscribe \
  --topic-arn "$ORDER_EVENTS_TOPIC_ARN" \
  --protocol sqs \
  --notification-endpoint "$NOTIFICATION_QUEUE_ARN"

echo "LocalStack initialization complete!"
