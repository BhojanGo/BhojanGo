variable "name" {
  type = string
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "kms_key_arn" {
  type = string
}

variable "stripe_secret_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "stripe_webhook_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "razorpay_key_id" {
  type    = string
  default = ""
}

variable "razorpay_key_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "twilio_account_sid" {
  type    = string
  default = ""
}

variable "twilio_auth_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "twilio_from_number" {
  type    = string
  default = ""
}

variable "sendgrid_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "firebase_project_id" {
  type    = string
  default = ""
}

variable "firebase_credentials_json" {
  type      = string
  default   = ""
  sensitive = true
}

variable "tags" {
  type = map(string)
}
