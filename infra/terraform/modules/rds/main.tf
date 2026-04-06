# ──────────────────────────────────────────────
# RDS PostgreSQL 16 — Multi-AZ in production
# ──────────────────────────────────────────────

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "${var.name}/rds/credentials"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = "bhojango"
    password = random_password.db.result
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = "bhojango"
    url      = "postgresql+asyncpg://bhojango:${random_password.db.result}@${aws_db_instance.main.address}:5432/bhojango"
  })
}

resource "aws_db_parameter_group" "pg16" {
  name_prefix = "${var.name}-pg16-"
  family      = "postgres16"
  tags        = var.tags

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  lifecycle { create_before_destroy = true }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.name}-postgres"
  engine         = "postgres"
  engine_version = "16.3"

  instance_class        = var.environment == "prod" ? "db.r6g.large" : "db.t4g.medium"
  allocated_storage     = var.environment == "prod" ? 100 : 20
  max_allocated_storage = var.environment == "prod" ? 500 : 50
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "bhojango"
  username = "bhojango"
  password = random_password.db.result

  multi_az               = var.environment == "prod"
  db_subnet_group_name   = var.subnet_group_name
  vpc_security_group_ids = [var.security_group_id]
  parameter_group_name   = aws_db_parameter_group.pg16.name

  backup_retention_period = var.environment == "prod" ? 14 : 3
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  deletion_protection       = var.environment == "prod"
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.name}-final-snapshot" : null
  copy_tags_to_snapshot     = true

  performance_insights_enabled = var.environment == "prod"
  monitoring_interval          = var.environment == "prod" ? 60 : 0

  tags = merge(var.tags, { Name = "${var.name}-postgres" })
}
