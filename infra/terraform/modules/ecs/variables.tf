variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
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

variable "services" {
  type = list(string)
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

variable "jwt_secret_arn" {
  type = string
}

variable "redis_endpoint" {
  type = string
}

variable "opensearch_endpoint" {
  type = string
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

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "tags" {
  type = map(string)
}
