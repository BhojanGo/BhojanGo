variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "subnet_group_name" {
  type = string
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
