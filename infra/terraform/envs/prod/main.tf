provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "BhojanGo"
      Environment = "prod"
      ManagedBy   = "Terraform"
    }
  }
}

module "platform" {
  source = "../../modules/platform"

  environment     = "prod"
  aws_region      = var.aws_region
  certificate_arn = var.certificate_arn
  cors_origins    = var.cors_origins
  desired_count   = 2

  waf_rate_limit_per_5min = 2000
}
