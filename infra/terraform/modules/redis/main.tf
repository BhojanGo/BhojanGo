# ──────────────────────────────────────────────
# ElastiCache Redis 7 — cluster mode in production
# ──────────────────────────────────────────────

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.name}-redis"
  description          = "BhojanGo Redis cluster"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.environment == "prod" ? "cache.r7g.large" : "cache.t4g.medium"
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name

  num_cache_clusters   = var.environment == "prod" ? 3 : 1
  automatic_failover_enabled = var.environment == "prod"
  multi_az_enabled           = var.environment == "prod"

  subnet_group_name  = var.subnet_group_name
  security_group_ids = [var.security_group_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.environment == "prod" ? random_password.redis_auth.result : null

  snapshot_retention_limit = var.environment == "prod" ? 7 : 0
  snapshot_window          = "02:00-03:00"
  maintenance_window       = "Mon:03:00-Mon:04:00"

  auto_minor_version_upgrade = true

  tags = merge(var.tags, { Name = "${var.name}-redis" })
}

resource "random_password" "redis_auth" {
  length  = 64
  special = false
}

resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.name}-redis7"
  family = "redis7"
  tags   = var.tags

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }
}
