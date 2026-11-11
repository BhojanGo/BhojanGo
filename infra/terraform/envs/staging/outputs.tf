output "alb_dns_name" {
  value = module.platform.alb_dns_name
}

output "ecr_repo_urls" {
  value = module.platform.ecr_repo_urls
}

output "ecs_cluster_name" {
  value = module.platform.ecs_cluster_name
}

output "ecs_service_names" {
  value = module.platform.ecs_service_names
}

output "app_secret_arns" {
  value = module.platform.app_secret_arns
}

output "cloudwatch_dashboard" {
  value = module.platform.cloudwatch_dashboard
}
