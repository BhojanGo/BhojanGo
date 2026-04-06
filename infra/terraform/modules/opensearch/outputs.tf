output "endpoint" {
  value = aws_opensearch_domain.main.endpoint
}

output "dashboard_endpoint" {
  value = aws_opensearch_domain.main.dashboard_endpoint
}

output "domain_arn" {
  value = aws_opensearch_domain.main.arn
}
