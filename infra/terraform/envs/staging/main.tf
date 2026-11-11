provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "BhojanGo"
      Environment = "staging"
      ManagedBy   = "Terraform"
    }
  }
}

module "platform" {
  source = "../../modules/platform"

  environment     = "staging"
  aws_region      = var.aws_region
  certificate_arn = var.certificate_arn
  cors_origins    = var.cors_origins
  desired_count   = 1

  waf_rate_limit_per_5min = 2000
}
