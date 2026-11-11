variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "alb_sg_id" {
  type = string
}

variable "environment" {
  type = string
}

variable "certificate_arn" {
  type    = string
  default = ""
}

variable "logs_bucket_name" {
  type = string
}

variable "waf_rate_limit" {
  description = "Max requests per client IP per 5 minutes before WAF blocks."
  type        = number
  default     = 2000
}

variable "tags" {
  type = map(string)
}
