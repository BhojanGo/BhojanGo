variable "name" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ecs_sg_id" {
  type = string
}

variable "ecr_repo_urls" {
  type = map(string)
}

variable "target_group_arns" {
  type = map(string)
}

variable "execution_role_arn" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "db_secret_arn" {
  type = string
}

variable "redis_secret_arn" {
  type = string
}

variable "redis_endpoint" {
  type = string
}

variable "jwt_secret_arn" {
  type = string
}

variable "core_api_url" {
  description = "Where realtime reaches core_api's internal endpoints"
  type        = string
}

variable "jwks_url" {
  description = "core_api's JWKS (public token keys) for realtime and worker"
  type        = string
}

variable "app_secret_arns" {
  description = "Secret ARNs by name: stripe, razorpay, twilio, sendgrid, firebase."
  type        = map(string)
}

variable "sqs_queue_urls" {
  type = map(string)
}

variable "sns_topic_arns" {
  type = map(string)
}

variable "s3_bucket_name" {
  type = string
}

variable "cors_origins" {
  type = list(string)
}

variable "desired_count" {
  type = number
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "tags" {
  type = map(string)
}
