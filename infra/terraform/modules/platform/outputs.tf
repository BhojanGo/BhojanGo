output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "alb_dns_name" {
  description = "Point your DNS (or test with) this name. Paths route to core-api, realtime and worker."
  value       = module.alb.alb_dns_name
}

output "alb_zone_id" {
  value = module.alb.alb_zone_id
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "rds_secret_arn" {
  value = module.rds.secret_arn
}

output "redis_endpoint" {
  value = module.redis.endpoint
}

output "ecr_repo_urls" {
  value = module.ecr.repo_urls
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecs_service_names" {
  value = module.ecs.service_names
}

output "app_secret_arns" {
  description = "Fill these in Secrets Manager (see docs/runbooks/aws-setup.md)."
  value       = module.secrets.secret_arns
}

output "sns_topic_arns" {
  value = module.sqs_sns.topic_arns
}

output "sqs_queue_urls" {
  value = module.sqs_sns.queue_urls
}

output "uploads_bucket" {
  value = module.s3.uploads_bucket_name
}

output "cloudfront_domain" {
  value = module.s3.cloudfront_domain
}

output "cloudwatch_dashboard" {
  value = module.cloudwatch.dashboard_name
}

output "alerts_topic_arn" {
  value = module.cloudwatch.alerts_topic_arn
}
