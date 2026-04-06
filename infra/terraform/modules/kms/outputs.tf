output "key_arn" {
  value = aws_kms_key.main.arn
}

output "key_id" {
  value = aws_kms_key.main.key_id
}

output "alias_name" {
  value = aws_kms_alias.main.name
}
