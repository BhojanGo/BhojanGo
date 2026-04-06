output "uploads_bucket_name" {
  value = aws_s3_bucket.uploads.bucket
}

output "uploads_bucket_arn" {
  value = aws_s3_bucket.uploads.arn
}

output "assets_bucket_name" {
  value = aws_s3_bucket.assets.bucket
}

output "assets_bucket_arn" {
  value = aws_s3_bucket.assets.arn
}

output "logs_bucket_name" {
  value = aws_s3_bucket.logs.bucket
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.assets.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.assets.id
}

output "bucket_name" {
  description = "Primary uploads bucket name (backwards compat)"
  value       = aws_s3_bucket.uploads.bucket
}
