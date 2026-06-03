variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "security_group_id" {
  type = string
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "tags" {
  type = map(string)
}

variable "allowed_role_arns" {
  type        = list(string)
  default     = []
  description = "IAM role ARNs permitted to access the domain. When empty, access is scoped to this AWS account's root (the domain is also network-isolated by its VPC security group)."
}
