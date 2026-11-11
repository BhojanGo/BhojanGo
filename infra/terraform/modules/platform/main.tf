# ──────────────────────────────────────────────
# BhojanGo platform — everything one environment needs (ADR-011):
# VPC, ECS Fargate (core-api, realtime, worker), RDS PostgreSQL 16 + PostGIS,
# ElastiCache Redis, SQS/SNS, S3, ALB + WAF, ECR, Secrets Manager, CloudWatch.
# Used by envs/staging and envs/prod; nothing here is applied directly.
# ──────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }

locals {
  account_id = data.aws_caller_identity.current.account_id
  azs        = slice(data.aws_availability_zones.available.names, 0, 3)
  name       = "bhojango-${var.environment}"
  services   = ["core-api", "realtime", "worker"]
  tags = merge(var.tags, {
    Project     = "BhojanGo"
    Environment = var.environment
    ManagedBy   = "Terraform"
  })
}

# ── Networking ───────────────────────────────
module "vpc" {
  source = "../vpc"

  name        = local.name
  azs         = local.azs
  environment = var.environment
  tags        = local.tags
}

module "security_groups" {
  source = "../security_groups"

  name   = local.name
  vpc_id = module.vpc.vpc_id
  tags   = local.tags
}

# ── Encryption ───────────────────────────────
module "kms" {
  source = "../kms"

  name       = local.name
  account_id = local.account_id
  tags       = local.tags
}

# ── Container registry ───────────────────────
module "ecr" {
  source = "../ecr"

  name     = local.name
  services = local.services
  tags     = local.tags
}

# ── Data stores ──────────────────────────────
module "rds" {
  source = "../rds"

  name              = local.name
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.database_subnet_ids
  subnet_group_name = module.vpc.db_subnet_group_name
  security_group_id = module.security_groups.rds_sg_id
  environment       = var.environment
  tags              = local.tags
}

module "redis" {
  source = "../redis"

  name              = local.name
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnet_ids
  subnet_group_name = module.vpc.elasticache_subnet_group_name
  security_group_id = module.security_groups.redis_sg_id
  environment       = var.environment
  tags              = local.tags
}

# ── Messaging ────────────────────────────────
module "sqs_sns" {
  source = "../sqs_sns"

  name       = local.name
  kms_key_id = module.kms.key_id
  tags       = local.tags
}

# ── Storage & CDN ────────────────────────────
module "s3" {
  source = "../s3"

  name       = local.name
  account_id = local.account_id
  tags       = local.tags
}

# ── Secrets (values are set outside Terraform) ──
module "secrets" {
  source = "../secrets"

  name        = local.name
  environment = var.environment
  kms_key_arn = module.kms.key_arn
  tags        = local.tags
}

# ── IAM ──────────────────────────────────────
module "iam" {
  source = "../iam"

  name        = local.name
  account_id  = local.account_id
  aws_region  = var.aws_region
  kms_key_arn = module.kms.key_arn
  # Everything the tasks read at start-up, including the RDS and Redis credentials.
  secret_arns    = concat(values(module.secrets.secret_arns), [module.rds.secret_arn, module.redis.auth_secret_arn])
  sqs_queue_arns = values(module.sqs_sns.queue_arns)
  sns_topic_arns = values(module.sqs_sns.topic_arns)
  s3_bucket_arn  = module.s3.uploads_bucket_arn
  tags           = local.tags
}

# ── Load balancer + WAF ──────────────────────
module "alb" {
  source = "../alb"

  name              = local.name
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  alb_sg_id         = module.security_groups.alb_sg_id
  environment       = var.environment
  certificate_arn   = var.certificate_arn
  logs_bucket_name  = module.s3.logs_bucket_name
  waf_rate_limit    = var.waf_rate_limit_per_5min
  tags              = local.tags
}

# ── Compute (ECS Fargate) ────────────────────
module "ecs" {
  source = "../ecs"

  name               = local.name
  private_subnet_ids = module.vpc.private_subnet_ids
  ecs_sg_id          = module.security_groups.ecs_sg_id
  ecr_repo_urls      = module.ecr.repo_urls
  target_group_arns  = module.alb.target_group_arns
  execution_role_arn = module.iam.ecs_execution_role_arn
  task_role_arn      = module.iam.ecs_task_role_arn
  db_secret_arn      = module.rds.secret_arn
  redis_secret_arn   = module.redis.auth_secret_arn
  redis_endpoint     = module.redis.endpoint
  jwt_secret_arn     = module.secrets.jwt_secret_arn
  app_secret_arns    = module.secrets.secret_arns
  sqs_queue_urls     = module.sqs_sns.queue_urls
  sns_topic_arns     = module.sqs_sns.topic_arns
  s3_bucket_name     = module.s3.uploads_bucket_name
  cors_origins       = var.cors_origins
  desired_count      = var.desired_count
  environment        = var.environment
  aws_region         = var.aws_region
  tags               = local.tags
}

# ── Observability ────────────────────────────
module "cloudwatch" {
  source = "../cloudwatch"

  name           = local.name
  services       = local.services
  environment    = var.environment
  aws_region     = var.aws_region
  kms_key_arn    = module.kms.key_arn
  alb_arn_suffix = module.alb.alb_arn_suffix
  tags           = local.tags
}

# ── Values the deploy workflow reads (no Terraform needed in CI deploys) ──
resource "aws_ssm_parameter" "deploy" {
  for_each = {
    cluster            = module.ecs.cluster_name
    private_subnet_ids = join(",", module.vpc.private_subnet_ids)
    ecs_security_group = module.security_groups.ecs_sg_id
    ecr_registry       = split("/", module.ecr.repo_urls["core-api"])[0]
    alb_dns_name       = module.alb.alb_dns_name
  }

  name  = "/${local.name}/deploy/${each.key}"
  type  = "String"
  value = each.value
  tags  = local.tags
}
