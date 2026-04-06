terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "s3" {
    bucket = "bhojango-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ──────────────────────────────────────────────
# Data sources
# ──────────────────────────────────────────────
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }

locals {
  account_id = data.aws_caller_identity.current.account_id
  azs        = slice(data.aws_availability_zones.available.names, 0, 3)
  name       = "bhojango-${var.environment}"
  tags = {
    Project     = "BhojanGo"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ──────────────────────────────────────────────
# Networking
# ──────────────────────────────────────────────
module "vpc" {
  source = "./modules/vpc"

  name        = local.name
  azs         = local.azs
  environment = var.environment
  tags        = local.tags
}

module "security_groups" {
  source = "./modules/security_groups"

  name   = local.name
  vpc_id = module.vpc.vpc_id
  tags   = local.tags
}

# ──────────────────────────────────────────────
# Encryption
# ──────────────────────────────────────────────
module "kms" {
  source = "./modules/kms"

  name       = local.name
  account_id = local.account_id
  tags       = local.tags
}

# ──────────────────────────────────────────────
# Container Registry
# ──────────────────────────────────────────────
module "ecr" {
  source = "./modules/ecr"

  name     = local.name
  services = var.services
  tags     = local.tags
}

# ──────────────────────────────────────────────
# Data Stores
# ──────────────────────────────────────────────
module "rds" {
  source = "./modules/rds"

  name              = local.name
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.database_subnet_ids
  subnet_group_name = module.vpc.db_subnet_group_name
  security_group_id = module.security_groups.rds_sg_id
  environment       = var.environment
  tags              = local.tags
}

module "redis" {
  source = "./modules/redis"

  name              = local.name
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnet_ids
  subnet_group_name = module.vpc.elasticache_subnet_group_name
  security_group_id = module.security_groups.redis_sg_id
  environment       = var.environment
  tags              = local.tags
}

module "opensearch" {
  source = "./modules/opensearch"

  name              = local.name
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = slice(module.vpc.private_subnet_ids, 0, 2)
  security_group_id = module.security_groups.opensearch_sg_id
  environment       = var.environment
  tags              = local.tags
}

# ──────────────────────────────────────────────
# Messaging
# ──────────────────────────────────────────────
module "sqs_sns" {
  source = "./modules/sqs_sns"

  name       = local.name
  kms_key_id = module.kms.key_id
  tags       = local.tags
}

# ──────────────────────────────────────────────
# Storage & CDN
# ──────────────────────────────────────────────
module "s3" {
  source = "./modules/s3"

  name       = local.name
  account_id = local.account_id
  tags       = local.tags
}

# ──────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────
module "cognito" {
  source = "./modules/cognito"

  name              = local.name
  callback_urls     = var.cognito_callback_urls
  logout_urls       = var.cognito_logout_urls
  google_client_id  = var.google_client_id
  google_client_secret = var.google_client_secret
  tags              = local.tags
}

# ──────────────────────────────────────────────
# Secrets
# ──────────────────────────────────────────────
module "secrets" {
  source = "./modules/secrets"

  name        = local.name
  environment = var.environment
  kms_key_arn = module.kms.key_arn
  tags        = local.tags
}

# ──────────────────────────────────────────────
# IAM
# ──────────────────────────────────────────────
module "iam" {
  source = "./modules/iam"

  name                  = local.name
  account_id            = local.account_id
  aws_region            = var.aws_region
  kms_key_arn           = module.kms.key_arn
  secret_arns           = values(module.secrets.secret_arns)
  sqs_queue_arns        = values(module.sqs_sns.queue_arns)
  sns_topic_arns        = values(module.sqs_sns.topic_arns)
  s3_bucket_arn         = module.s3.uploads_bucket_arn
  opensearch_domain_arn = module.opensearch.domain_arn
  tags                  = local.tags
}

# ──────────────────────────────────────────────
# Load Balancer
# ──────────────────────────────────────────────
module "alb" {
  source = "./modules/alb"

  name              = local.name
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  alb_sg_id         = module.security_groups.alb_sg_id
  environment       = var.environment
  certificate_arn   = var.certificate_arn
  logs_bucket_name  = module.s3.logs_bucket_name
  tags              = local.tags
}

# ──────────────────────────────────────────────
# Compute (ECS Fargate)
# ──────────────────────────────────────────────
module "ecs" {
  source = "./modules/ecs"

  name                = local.name
  vpc_id              = module.vpc.vpc_id
  public_subnet_ids   = module.vpc.public_subnet_ids
  private_subnet_ids  = module.vpc.private_subnet_ids
  ecs_sg_id           = module.security_groups.ecs_sg_id
  ecr_repo_urls       = module.ecr.repo_urls
  services            = var.services
  target_group_arns   = module.alb.target_group_arns
  execution_role_arn  = module.iam.ecs_execution_role_arn
  task_role_arn       = module.iam.ecs_task_role_arn
  db_secret_arn       = module.rds.secret_arn
  jwt_secret_arn      = module.secrets.jwt_secret_arn
  redis_endpoint      = module.redis.endpoint
  opensearch_endpoint = module.opensearch.endpoint
  sqs_queue_urls      = module.sqs_sns.queue_urls
  sns_topic_arns      = module.sqs_sns.topic_arns
  s3_bucket_name      = module.s3.uploads_bucket_name
  environment         = var.environment
  aws_region          = var.aws_region
  account_id          = local.account_id
  tags                = local.tags
}

# ──────────────────────────────────────────────
# Observability
# ──────────────────────────────────────────────
module "cloudwatch" {
  source = "./modules/cloudwatch"

  name           = local.name
  services       = var.services
  environment    = var.environment
  aws_region     = var.aws_region
  kms_key_arn    = module.kms.key_arn
  alb_arn_suffix = module.alb.alb_arn_suffix
  tags           = local.tags
}
