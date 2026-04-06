# ──────────────────────────────────────────────
# ECS Fargate — cluster + task definitions + services
# ──────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "${var.name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name = "/ecs/${var.name}/exec"
      }
    }
  }

  tags = merge(var.tags, { Name = "${var.name}-cluster" })
}

resource "aws_cloudwatch_log_group" "ecs_exec" {
  name              = "/ecs/${var.name}/exec"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = var.environment == "prod" ? "FARGATE" : "FARGATE_SPOT"
    weight            = 1
    base              = var.environment == "prod" ? 1 : 0
  }
}

# ── Service Configuration ────────────────────
locals {
  service_config = {
    "user-svc" = {
      port   = 8001
      cpu    = var.environment == "prod" ? 512 : 256
      memory = var.environment == "prod" ? 1024 : 512
      env_extra = {
        REDIS_URL = "redis://${var.redis_endpoint}:6379/0"
      }
    }
    "restaurant-svc" = {
      port   = 8002
      cpu    = var.environment == "prod" ? 512 : 256
      memory = var.environment == "prod" ? 1024 : 512
      env_extra = {
        REDIS_URL           = "redis://${var.redis_endpoint}:6379/1"
        OPENSEARCH_URL      = "https://${var.opensearch_endpoint}"
        S3_BUCKET           = var.s3_bucket_name
      }
    }
    "order-svc" = {
      port   = 8003
      cpu    = var.environment == "prod" ? 512 : 256
      memory = var.environment == "prod" ? 1024 : 512
      env_extra = {
        REDIS_URL           = "redis://${var.redis_endpoint}:6379/2"
        SNS_TOPIC_ARN_ORDER = var.sns_topic_arns["order_events"]
      }
    }
    "delivery-svc" = {
      port   = 8004
      cpu    = var.environment == "prod" ? 512 : 256
      memory = var.environment == "prod" ? 1024 : 512
      env_extra = {
        REDIS_URL               = "redis://${var.redis_endpoint}:6379/3"
        SNS_TOPIC_ARN_DELIVERY  = var.sns_topic_arns["driver_events"]
      }
    }
    "payment-svc" = {
      port   = 8005
      cpu    = var.environment == "prod" ? 512 : 256
      memory = var.environment == "prod" ? 1024 : 512
      env_extra = {
        REDIS_URL              = "redis://${var.redis_endpoint}:6379/4"
        SNS_TOPIC_ARN_PAYMENT  = var.sns_topic_arns["payment_events"]
      }
    }
    "notification-svc" = {
      port   = 8006
      cpu    = var.environment == "prod" ? 512 : 256
      memory = var.environment == "prod" ? 1024 : 512
      env_extra = {
        SQS_QUEUE_URL_NOTIFICATION = var.sqs_queue_urls["notifications"]
      }
    }
  }
}

# ── Task Definitions ─────────────────────────
resource "aws_ecs_task_definition" "services" {
  for_each = local.service_config

  family                   = "${var.name}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name      = each.key
    image     = "${var.ecr_repo_urls[each.key]}:latest"
    essential = true

    portMappings = [{
      containerPort = each.value.port
      protocol      = "tcp"
    }]

    environment = concat(
      [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "AWS_DEFAULT_REGION", value = var.aws_region },
        { name = "SERVICE_NAME", value = each.key },
        { name = "PORT", value = tostring(each.value.port) }
      ],
      [for k, v in each.value.env_extra : { name = k, value = v }]
    )

    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = "${var.db_secret_arn}:url::"
      },
      {
        name      = "JWT_SECRET"
        valueFrom = "${var.jwt_secret_arn}:secret::"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/${var.name}/${each.key}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:${each.value.port}/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })
}

# ── ECS Services ─────────────────────────────
resource "aws_ecs_service" "services" {
  for_each = local.service_config

  name            = "${var.name}-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services[each.key].arn
  desired_count   = var.environment == "prod" ? 2 : 1
  launch_type     = var.environment == "prod" ? "FARGATE" : null

  dynamic "capacity_provider_strategy" {
    for_each = var.environment != "prod" ? [1] : []
    content {
      capacity_provider = "FARGATE_SPOT"
      weight            = 1
    }
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arns[each.key]
    container_name   = each.key
    container_port   = each.value.port
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_controller {
    type = "ECS"
  }

  force_new_deployment = false
  enable_execute_command = true

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })

  lifecycle {
    ignore_changes = [desired_count, task_definition]
  }
}

# ── Auto Scaling ─────────────────────────────
resource "aws_appautoscaling_target" "services" {
  for_each = var.environment == "prod" ? local.service_config : {}

  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.services[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  for_each = var.environment == "prod" ? local.service_config : {}

  name               = "${var.name}-${each.key}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.services[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.services[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.services[each.key].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
