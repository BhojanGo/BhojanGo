variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "certificate_arn" {
  description = "ACM certificate for the ALB. Leave empty until DNS exists (HTTP only)."
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "Web and admin origins allowed by the backend CORS policy. Set your real domains when DNS exists."
  type        = list(string)
  default     = []
}
