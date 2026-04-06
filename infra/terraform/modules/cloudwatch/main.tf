# ──────────────────────────────────────────────
# CloudWatch — log groups + dashboards + alarms
# ──────────────────────────────────────────────

# ── Log Groups (one per service) ─────────────
resource "aws_cloudwatch_log_group" "services" {
  for_each = toset(var.services)

  name              = "/${var.name}/${each.key}"
  retention_in_days = var.environment == "prod" ? 90 : 14
  kms_key_id        = var.kms_key_arn
  tags              = merge(var.tags, { Name = "${var.name}-${each.key}-logs" })
}

# ── Dashboard ────────────────────────────────
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name}-overview"

  dashboard_body = jsonencode({
    widgets = concat(
      # Row 1: Service health
      [for i, svc in var.services : {
        type   = "metric"
        x      = (i % 3) * 8
        y      = floor(i / 3) * 6
        width  = 8
        height = 6
        properties = {
          title  = "${svc} — Request Count & Errors"
          region = var.aws_region
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", "${var.name}-${svc}", "ClusterName", "${var.name}-cluster",
              { stat = "Average", period = 300 }],
            ["AWS/ECS", "MemoryUtilization", "ServiceName", "${var.name}-${svc}", "ClusterName", "${var.name}-cluster",
              { stat = "Average", period = 300 }]
          ]
          view   = "timeSeries"
          stacked = false
        }
      }],
      # Row 3: Database
      [{
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "RDS — CPU & Connections"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "${var.name}-postgres",
              { stat = "Average", period = 300 }],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", "${var.name}-postgres",
              { stat = "Sum", period = 300 }]
          ]
          view = "timeSeries"
        }
      }],
      # Redis
      [{
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Redis — Cache Hit Rate"
          region = var.aws_region
          metrics = [
            ["AWS/ElastiCache", "CacheHits", "ReplicationGroupId", "${var.name}-redis",
              { stat = "Sum", period = 300 }],
            ["AWS/ElastiCache", "CacheMisses", "ReplicationGroupId", "${var.name}-redis",
              { stat = "Sum", period = 300 }]
          ]
          view = "timeSeries"
        }
      }],
      # ALB
      [{
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "ALB — Request Count & Latency"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix,
              { stat = "Sum", period = 60 }],
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix,
              { stat = "p99", period = 60 }]
          ]
          view = "timeSeries"
        }
      }],
      [{
        type   = "metric"
        x      = 12
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "ALB — HTTP 5xx Errors"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix,
              { stat = "Sum", period = 60, color = "#d62728" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer", var.alb_arn_suffix,
              { stat = "Sum", period = 60, color = "#ff7f0e" }]
          ]
          view = "timeSeries"
        }
      }]
    )
  })
}

# ── SNS Alert Topic ──────────────────────────
resource "aws_sns_topic" "alerts" {
  name = "${var.name}-alerts"
  tags = var.tags
}

# ── Critical Alarms ──────────────────────────
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  for_each = toset(var.services)

  alarm_name          = "${var.name}-${each.key}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "CPU > 80% for ${each.key}"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = "${var.name}-cluster"
    ServiceName = "${var.name}-${each.key}"
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.name}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "ALB 5xx errors > 10/min"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.name}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU > 80%"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = "${var.name}-postgres"
  }

  tags = var.tags
}
