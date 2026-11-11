terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state in S3 with a DynamoDB lock (created by infra/terraform/bootstrap).
  # Partial config: key/region/table are in backend.hcl; the bucket name includes
  # your account id and is passed at init:
  #   terraform init -backend-config=backend.hcl -backend-config="bucket=<TF_STATE_BUCKET>"
  backend "s3" {}
}
