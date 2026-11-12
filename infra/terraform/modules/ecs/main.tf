# ──────────────────────────────────────────────
# ECS Fargate — cluster + the three deployables (ADR-011):
#   core-api :8001, realtime :8004, worker :8006
#
# Terraform creates the first task definition revision (image tag
# "bootstrap"); after that, CI registers new revisions with the commit's
# image and updates the services (see .github/workflows/deploy.yml), so the
# services ignore task_definition changes here.
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
        cloud_watch_log_group_name = aws_cloudwatch_log_group.ecs_exec.name
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

locals {
  is_prod = var.environment == "prod"
  app_env = local.is_prod ? "production" : "staging"

  # "<secret arn>:<json key>::" is how ECS reads one key of a JSON secret.
  secret = {
    database_url          = "${var.db_secret_arn}:url::"
    jwt_private_key       = "${var.jwt_secret_arn}:private_key::"
    internal_secret       = "${var.jwt_secret_arn}:internal_secret::"
    redis_password        = "${var.redis_secret_arn}:password::"
    stripe_secret_key     = "${var.app_secret_arns["stripe"]}:secret_key::"
    stripe_webhook_secret = "${var.app_secret_arns["stripe"]}:webhook_secret::"
    stripe_publishable    = "${var.app_secret_arns["stripe"]}:publishable_key::"
    razorpay_key_id       = "${var.app_secret_arns["razorpay"]}:key_id::"
    razorpay_key_secret   = "${var.app_secret_arns["razorpay"]}:key_secret::"
    razorpay_webhook      = "${var.app_secret_arns["razorpay"]}:webhook_secret::"
    twilio_sid            = "${var.app_secret_arns["twilio"]}:account_sid::"
    twilio_token          = "${var.app_secret_arns["twilio"]}:auth_token::"
    twilio_from_us        = "${var.app_secret_arns["twilio"]}:from_number_us::"
    twilio_from_in        = "${var.app_secret_arns["twilio"]}:from_number_in::"
    sendgrid_api_key      = "${var.app_secret_arns["sendgrid"]}:api_key::"
    firebase_project_id   = "${var.app_secret_arns["firebase"]}:project_id::"
    firebase_key_id       = "${var.app_secret_arns["firebase"]}:private_key_id::"
    firebase_key          = "${var.app_secret_arns["firebase"]}:private_key::"
    firebase_email        = "${var.app_secret_arns["firebase"]}:client_email::"
  }

  common_env = {
    APP_ENV      = local.app_env
    AWS_REGION   = var.aws_region
    CORS_ORIGINS = jsonencode(var.cors_origins)
    LOG_LEVEL    = "INFO"
  }

  services = {
    "core-api" = {
      port   = 8001
      cpu    = local.is_prod ? 1024 : 512
      memory = local.is_prod ? 2048 : 1024
      # Migrations run once per deploy as a separate task, not in every container.
      command = ["uvicorn", "core_api.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
      env = {
        SERVICE_NAME          = "core-api"
        REDIS_URL             = "rediss://${var.redis_endpoint}:6379/0"
        SNS_TOPIC_ARN_ORDER   = var.sns_topic_arns["order_events"]
        SNS_TOPIC_ARN_PAYMENT = var.sns_topic_arns["payment_events"]
        AWS_S3_BUCKET         = var.s3_bucket_name
      }
      secrets = {
        DATABASE_URL            = local.secret.database_url
        JWT_PRIVATE_KEY         = local.secret.jwt_private_key
        INTERNAL_SERVICE_SECRET = local.secret.internal_secret
        REDIS_PASSWORD          = local.secret.redis_password
        STRIPE_SECRET_KEY       = local.secret.stripe_secret_key
        STRIPE_WEBHOOK_SECRET   = local.secret.stripe_webhook_secret
        STRIPE_PUBLISHABLE_KEY  = local.secret.stripe_publishable
        RAZORPAY_KEY_ID         = local.secret.razorpay_key_id
        RAZORPAY_KEY_SECRET     = local.secret.razorpay_key_secret
        RAZORPAY_WEBHOOK_SECRET = local.secret.razorpay_webhook
        TWILIO_ACCOUNT_SID      = local.secret.twilio_sid
        TWILIO_AUTH_TOKEN       = local.secret.twilio_token
        TWILIO_PHONE_NUMBER     = local.secret.twilio_from_us
        TWILIO_PHONE_NUMBER_IN  = local.secret.twilio_from_in
      }
    }
    "realtime" = {
      port    = 8004
      cpu     = local.is_prod ? 512 : 256
      memory  = local.is_prod ? 1024 : 512
      command = null
      env = {
        SERVICE_NAME           = "realtime"
        REDIS_URL              = "rediss://${var.redis_endpoint}:6379/3"
        SNS_TOPIC_ARN_DELIVERY = var.sns_topic_arns["driver_events"]
        JWKS_URL               = var.jwks_url
        # Dispatch (P14): order events in, signed calls out to core_api.
        SQS_QUEUE_URL_ORDERS = var.sqs_queue_urls["order_events"]
        CORE_API_URL         = var.core_api_url
      }
      secrets = {
        REDIS_PASSWORD          = local.secret.redis_password
        INTERNAL_SERVICE_SECRET = local.secret.internal_secret
      }
    }
    "worker" = {
      port    = 8006
      cpu     = local.is_prod ? 512 : 256
      memory  = local.is_prod ? 1024 : 512
      command = null
      env = {
        SERVICE_NAME               = "worker"
        DB_POOL_SIZE               = "5"
        SQS_QUEUE_URL_NOTIFICATION = var.sqs_queue_urls["notifications"]
        JWKS_URL                   = var.jwks_url
        # The outbox relay (P11) publishes order/payment events to these topics.
        SNS_TOPIC_ARN_ORDER    = var.sns_topic_arns["order_events"]
        SNS_TOPIC_ARN_PAYMENT  = var.sns_topic_arns["payment_events"]
        SNS_TOPIC_ARN_DELIVERY = var.sns_topic_arns["driver_events"]
      }
      secrets = {
        DATABASE_URL            = local.secret.database_url
        TWILIO_ACCOUNT_SID      = local.secret.twilio_sid
        TWILIO_AUTH_TOKEN       = local.secret.twilio_token
        TWILIO_PHONE_NUMBER     = local.secret.twilio_from_us
        TWILIO_PHONE_NUMBER_IN  = local.secret.twilio_from_in
        SENDGRID_API_KEY        = local.secret.sendgrid_api_key
        FIREBASE_PROJECT_ID     = local.secret.firebase_project_id
        FIREBASE_PRIVATE_KEY_ID = local.secret.firebase_key_id
        FIREBASE_PRIVATE_KEY    = local.secret.firebase_key
        FIREBASE_CLIENT_EMAIL   = local.secret.firebase_email
      }
    }
  }
}

# ── Task definitions (first revision; CI registers later ones) ──
resource "aws_ecs_task_definition" "services" {
  for_each = local.services

  family                   = "${var.name}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([merge(
    {
      name      = each.key
      image     = "${var.ecr_repo_urls[each.key]}:bootstrap"
      essential = true

      portMappings = [{ containerPort = each.value.port, protocol = "tcp" }]

      environment = [for k, v in merge(local.common_env, each.value.env) : { name = k, value = v }]
      secrets     = [for k, v in each.value.secrets : { name = k, valueFrom = v }]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/${var.name}/${each.key}"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # The images are python:3.12-slim (no curl).
      healthCheck = {
        command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:${each.value.port}/health/live')"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    },
    each.value.command == null ? {} : { command = each.value.command }
  )])

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })
}

# ── Services ─────────────────────────────────
resource "aws_ecs_service" "services" {
  for_each = local.services

  name            = "${var.name}-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services[each.key].arn
  desired_count   = local.is_prod ? max(var.desired_count, 2) : var.desired_count
  launch_type     = local.is_prod ? "FARGATE" : null

  dynamic "capacity_provider_strategy" {
    for_each = local.is_prod ? [] : [1]
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

  health_check_grace_period_seconds = 60

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_controller {
    type = "ECS"
  }

  enable_execute_command = true

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })

  lifecycle {
    # CI owns the running revision (image tag) and autoscaling owns the count.
    ignore_changes = [desired_count, task_definition]
  }
}

# ── Auto scaling (prod) ──────────────────────
resource "aws_appautoscaling_target" "services" {
  for_each = local.is_prod ? local.services : {}

  max_capacity       = 10
  min_capacity       = max(var.desired_count, 2)
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.services[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  for_each = local.is_prod ? local.services : {}

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
