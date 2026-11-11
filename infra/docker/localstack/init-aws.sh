#!/bin/bash
# LocalStack init (runs once LocalStack is ready; safe to run again).
# Creates the queues, topics and buckets the backend uses locally, matching
# the names in compose.yaml. Event flow: core_api publishes to the SNS topics,
# the notification queue receives order and payment events, and the worker
# consumes it (core_api also puts notify.send messages straight on it).
set -euo pipefail

aws() { awslocal "$@"; }
ACCOUNT=000000000000
REGION=us-east-1

queue_arn() { echo "arn:aws:sqs:${REGION}:${ACCOUNT}:$1"; }

for q in order payment notification delivery; do
  aws sqs create-queue --queue-name "bhojango-${q}-events-dlq" >/dev/null
  redrive="{\"deadLetterTargetArn\":\"$(queue_arn "bhojango-${q}-events-dlq")\",\"maxReceiveCount\":\"3\"}"
  aws sqs create-queue --queue-name "bhojango-${q}-events" \
    --attributes "{\"RedrivePolicy\":$(printf '%s' "$redrive" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" >/dev/null
done

for t in order payment driver notification user; do
  aws sns create-topic --name "bhojango-${t}-topic" >/dev/null
done

topic_arn() { echo "arn:aws:sns:${REGION}:${ACCOUNT}:bhojango-$1-topic"; }
for t in order payment; do
  aws sns subscribe --topic-arn "$(topic_arn "$t")" --protocol sqs \
    --notification-endpoint "$(queue_arn bhojango-notification-events)" >/dev/null
done
aws sns subscribe --topic-arn "$(topic_arn order)" --protocol sqs \
  --notification-endpoint "$(queue_arn bhojango-order-events)" >/dev/null
aws sns subscribe --topic-arn "$(topic_arn driver)" --protocol sqs \
  --notification-endpoint "$(queue_arn bhojango-delivery-events)" >/dev/null

for b in bhojango-uploads bhojango-assets bhojango-assets-dev; do
  aws s3 mb "s3://$b" >/dev/null 2>&1 || true
done

echo "LocalStack ready: $(aws sqs list-queues --query 'length(QueueUrls)') queues, buckets: $(aws s3 ls | wc -l)"
