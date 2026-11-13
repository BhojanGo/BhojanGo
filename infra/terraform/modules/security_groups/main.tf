# ──────────────────────────────────────────────
# Security Groups — least-privilege network access
# ──────────────────────────────────────────────

# ── ALB Security Group ───────────────────────
resource "aws_security_group" "alb" {
  name_prefix = "${var.name}-alb-"
  vpc_id      = var.vpc_id
  description = "ALB — allow HTTP/HTTPS from internet"
  tags        = merge(var.tags, { Name = "${var.name}-alb-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

# Security pass (trivy AVD-AWS-0104): the load balancer only talks to the services.
resource "aws_vpc_security_group_egress_rule" "alb_all" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.ecs.id
  ip_protocol                  = "-1"
}

# ── ECS Tasks Security Group ────────────────
resource "aws_security_group" "ecs" {
  name_prefix = "${var.name}-ecs-"
  vpc_id      = var.vpc_id
  description = "ECS tasks — allow traffic from ALB only"
  tags        = merge(var.tags, { Name = "${var.name}-ecs-sg" })

  lifecycle { create_before_destroy = true }
}

# core-api 8001, realtime 8004, worker 8006
resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  for_each = toset(["8001", "8004", "8006"])

  security_group_id            = aws_security_group.ecs.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = tonumber(each.key)
  to_port                      = tonumber(each.key)
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "ecs_all" {
  security_group_id = aws_security_group.ecs.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# ── RDS Security Group ──────────────────────
resource "aws_security_group" "rds" {
  name_prefix = "${var.name}-rds-"
  vpc_id      = var.vpc_id
  description = "RDS — allow PostgreSQL from ECS tasks only"
  tags        = merge(var.tags, { Name = "${var.name}-rds-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_ecs" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

# ── Redis Security Group ────────────────────
resource "aws_security_group" "redis" {
  name_prefix = "${var.name}-redis-"
  vpc_id      = var.vpc_id
  description = "Redis — allow access from ECS tasks only"
  tags        = merge(var.tags, { Name = "${var.name}-redis-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_ecs" {
  security_group_id            = aws_security_group.redis.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}
