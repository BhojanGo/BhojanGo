output "endpoint" {
  value = aws_db_instance.main.address
}

output "port" {
  value = aws_db_instance.main.port
}

output "secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "db_instance_id" {
  value = aws_db_instance.main.id
}
