output "log_group_names" {
  value = { for k, v in aws_cloudwatch_log_group.services : k => v.name }
}

output "log_group_arns" {
  value = { for k, v in aws_cloudwatch_log_group.services : k => v.arn }
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "dashboard_name" {
  value = aws_cloudwatch_dashboard.main.dashboard_name
}
