variable "name" {
  type = string
}

variable "account_id" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "secret_arns" {
  type = list(string)
}

variable "sqs_queue_arns" {
  type = list(string)
}

variable "sns_topic_arns" {
  type = list(string)
}

variable "s3_bucket_arn" {
  type = string
}

variable "opensearch_domain_arn" {
  type = string
}

variable "tags" {
  type = map(string)
}
