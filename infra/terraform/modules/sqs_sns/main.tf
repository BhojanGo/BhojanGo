# ──────────────────────────────────────────────
# SQS Queues + SNS Topics — event-driven architecture
# ──────────────────────────────────────────────

locals {
  topics = {
    order_events   = "${var.name}-order-events"
    payment_events = "${var.name}-payment-events"
    driver_events  = "${var.name}-driver-events"
  }

  queues = {
    notifications = "${var.name}-notifications"
    order_events  = "${var.name}-order-events"
  }
}

# ── SNS Topics ───────────────────────────────
resource "aws_sns_topic" "topics" {
  for_each = local.topics

  name              = each.value
  kms_master_key_id = var.kms_key_id
  tags              = merge(var.tags, { Name = each.value })
}

# ── SQS Dead-Letter Queues ──────────────────
resource "aws_sqs_queue" "dlq" {
  for_each = local.queues

  name                      = "${each.value}-dlq"
  message_retention_seconds = 1209600 # 14 days
  kms_master_key_id         = var.kms_key_id
  tags                      = merge(var.tags, { Name = "${each.value}-dlq" })
}

# ── SQS Queues ───────────────────────────────
resource "aws_sqs_queue" "queues" {
  for_each = local.queues

  name                       = each.value
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20     # long polling
  kms_master_key_id          = var.kms_key_id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 3
  })

  tags = merge(var.tags, { Name = each.value })
}

# ── SNS → SQS Subscriptions ─────────────────
resource "aws_sns_topic_subscription" "order_to_notifications" {
  topic_arn = aws_sns_topic.topics["order_events"].arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.queues["notifications"].arn
}

resource "aws_sns_topic_subscription" "payment_to_notifications" {
  topic_arn = aws_sns_topic.topics["payment_events"].arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.queues["notifications"].arn
}

resource "aws_sns_topic_subscription" "order_to_order_events" {
  topic_arn = aws_sns_topic.topics["order_events"].arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.queues["order_events"].arn
}

# ── SQS Policies (allow SNS to send) ────────
resource "aws_sqs_queue_policy" "allow_sns" {
  for_each  = local.queues
  queue_url = aws_sqs_queue.queues[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowSNS"
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.queues[each.key].arn
      Condition = {
        ArnLike = {
          "aws:SourceArn" = "arn:aws:sns:*:*:${var.name}-*"
        }
      }
    }]
  })
}
