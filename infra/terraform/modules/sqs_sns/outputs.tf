output "topic_arns" {
  value = { for k, v in aws_sns_topic.topics : k => v.arn }
}

output "queue_urls" {
  value = { for k, v in aws_sqs_queue.queues : k => v.url }
}

output "queue_arns" {
  value = { for k, v in aws_sqs_queue.queues : k => v.arn }
}

output "dlq_arns" {
  value = { for k, v in aws_sqs_queue.dlq : k => v.arn }
}
