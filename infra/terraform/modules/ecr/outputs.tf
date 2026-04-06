output "repo_urls" {
  value = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "repo_arns" {
  value = { for k, v in aws_ecr_repository.services : k => v.arn }
}
