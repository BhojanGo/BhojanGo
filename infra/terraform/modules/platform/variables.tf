variable "aws_region" {
  type = string
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "environment must be staging or prod."
  }
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS on the ALB. Empty = HTTP only (fine for a first staging deploy)."
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "Origins allowed by the backend's CORS middleware (web and admin URLs)."
  type        = list(string)
  default     = []
}

variable "desired_count" {
  description = "Tasks per ECS service. Prod also autoscales from this minimum."
  type        = number
  default     = 1
}

variable "waf_rate_limit_per_5min" {
  description = "WAF rate-based rule: max requests per client IP per 5 minutes."
  type        = number
  default     = 2000
}

variable "tags" {
  type    = map(string)
  default = {}
}
