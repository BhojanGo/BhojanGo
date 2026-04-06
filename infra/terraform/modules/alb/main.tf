# ──────────────────────────────────────────────
# ALB — Application Load Balancer + target groups
# ──────────────────────────────────────────────

resource "aws_lb" "main" {
  name               = "${var.name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = var.environment == "prod"

  access_logs {
    bucket  = var.logs_bucket_name
    prefix  = "alb"
    enabled = true
  }

  tags = merge(var.tags, { Name = "${var.name}-alb" })
}

# ── HTTPS Listener ───────────────────────────
resource "aws_lb_listener" "https" {
  count = var.certificate_arn != "" ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = "{\"error\":\"not_found\"}"
      status_code  = "404"
    }
  }
}

# ── HTTP Listener (redirect to HTTPS) ───────
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = var.certificate_arn != "" ? "redirect" : "fixed-response"

    dynamic "redirect" {
      for_each = var.certificate_arn != "" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "fixed_response" {
      for_each = var.certificate_arn == "" ? [1] : []
      content {
        content_type = "application/json"
        message_body = "{\"error\":\"not_found\"}"
        status_code  = "404"
      }
    }
  }
}

# ── Target Groups (one per service) ──────────
locals {
  service_ports = {
    "user-svc"         = 8001
    "restaurant-svc"   = 8002
    "order-svc"        = 8003
    "delivery-svc"     = 8004
    "payment-svc"      = 8005
    "notification-svc" = 8006
  }
}

resource "aws_lb_target_group" "services" {
  for_each = local.service_ports

  name        = "${var.name}-${each.key}"
  port        = each.value
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  deregistration_delay = 30
  tags                 = merge(var.tags, { Name = "${var.name}-${each.key}-tg" })
}

# ── Listener Rules (path-based routing) ──────
locals {
  service_routes = {
    "user-svc"         = ["/api/v1/auth/*", "/api/v1/users/*"]
    "restaurant-svc"   = ["/api/v1/restaurants/*", "/api/v1/search/*"]
    "order-svc"        = ["/api/v1/orders/*"]
    "delivery-svc"     = ["/api/v1/delivery/*", "/ws/*"]
    "payment-svc"      = ["/api/v1/payments/*", "/api/v1/wallet/*"]
    "notification-svc" = ["/api/v1/notifications/*"]
  }
}

resource "aws_lb_listener_rule" "services" {
  for_each = local.service_routes

  listener_arn = var.certificate_arn != "" ? aws_lb_listener.https[0].arn : aws_lb_listener.http.arn
  priority     = 100 + index(keys(local.service_routes), each.key)

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services[each.key].arn
  }

  condition {
    path_pattern {
      values = each.value
    }
  }
}
