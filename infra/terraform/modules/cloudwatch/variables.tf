variable "name" {
  type = string
}

variable "services" {
  type = list(string)
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "alb_arn_suffix" {
  type = string
}

variable "tags" {
  type = map(string)
}
