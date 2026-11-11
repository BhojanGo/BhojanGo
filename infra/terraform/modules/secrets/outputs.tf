output "secret_arns" {
  description = "App secret ARNs by name (stripe, razorpay, twilio, sendgrid, firebase) plus jwt."
  value       = merge({ for k, v in aws_secretsmanager_secret.app : k => v.arn }, { jwt = aws_secretsmanager_secret.jwt.arn })
}

output "jwt_secret_arn" {
  value = aws_secretsmanager_secret.jwt.arn
}
