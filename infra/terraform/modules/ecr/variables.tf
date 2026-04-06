variable "name" {
  type = string
}

variable "services" {
  type = list(string)
}

variable "tags" {
  type = map(string)
}
