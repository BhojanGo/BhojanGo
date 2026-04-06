variable "name" {
  type = string
}

variable "azs" {
  type = list(string)
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "environment" {
  type = string
}

variable "tags" {
  type = map(string)
}
