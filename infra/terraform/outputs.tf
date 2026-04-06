# ──────────────────────────────────────────────
# Outputs — all important resource endpoints & ARNs
# ──────────────────────────────────────────────

# ── Networking ───────────────────────────────
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "public_subnet_ids" {
  value = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

# ── Load Balancer ────────────────────────────
output "alb_dns_name" {
  description = "ALB DNS name — point your domain here"
  value       = module.alb.alb_dns_name
}

output "alb_zone_id" {
  value = module.alb.alb_zone_id
}

# ── Database ─────────────────────────────────
output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "rds_secret_arn" {
  value = module.rds.secret_arn
}

# ── Cache ────────────────────────────────────
output "redis_endpoint" {
  value = module.redis.endpoint
}

output "redis_reader_endpoint" {
  value = module.redis.reader_endpoint
}

# ── Search ───────────────────────────────────
output "opensearch_endpoint" {
  value = module.opensearch.endpoint
}

output "opensearch_dashboard" {
  value = module.opensearch.dashboard_endpoint
}

# ── Container Registry ──────────────────────
output "ecr_repo_urls" {
  value = module.ecr.repo_urls
}

# ── Compute ──────────────────────────────────
output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecs_service_names" {
  value = module.ecs.service_names
}

# ── Messaging ────────────────────────────────
output "sns_topic_arns" {
  value = module.sqs_sns.topic_arns
}

output "sqs_queue_urls" {
  value = module.sqs_sns.queue_urls
}

# ── Storage ──────────────────────────────────
output "uploads_bucket" {
  value = module.s3.uploads_bucket_name
}

output "cloudfront_domain" {
  value = module.s3.cloudfront_domain
}

# ── Auth ─────────────────────────────────────
output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_web_client_id" {
  value = module.cognito.web_client_id
}

output "cognito_mobile_client_id" {
  value = module.cognito.mobile_client_id
}

# ── Observability ────────────────────────────
output "cloudwatch_dashboard" {
  value = module.cloudwatch.dashboard_name
}

output "alerts_topic_arn" {
  value = module.cloudwatch.alerts_topic_arn
}
