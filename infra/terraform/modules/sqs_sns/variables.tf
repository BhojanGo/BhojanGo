variable "name" {
  type = string
}

variable "kms_key_id" {
  type    = string
  default = "alias/aws/sqs"
}

variable "tags" {
  type = map(string)
}
