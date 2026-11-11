# ──────────────────────────────────────────────
# Secrets Manager — application secrets
#
# Terraform creates each secret with every key the ECS tasks read, set to a
# placeholder, and then ignores the value. Real values (Stripe, Razorpay,
# Twilio, SendGrid, Firebase) are set in Secrets Manager by a person (see
# docs/runbooks/aws-setup.md), so they never pass through Terraform or its
# state. The JWT secret is generated here.
# ──────────────────────────────────────────────

locals {
  placeholders = {
    stripe = {
      description = "Stripe API keys (US)"
      keys        = ["secret_key", "webhook_secret"]
    }
    razorpay = {
      description = "Razorpay API keys (India)"
      keys        = ["key_id", "key_secret", "webhook_secret"]
    }
    twilio = {
      description = "Twilio SMS/OTP credentials"
      keys        = ["account_sid", "auth_token", "from_number_us", "from_number_in"]
    }
    sendgrid = {
      description = "SendGrid email API key"
      keys        = ["api_key"]
    }
    firebase = {
      description = "Firebase service account for FCM push"
      keys        = ["project_id", "private_key_id", "private_key", "client_email"]
    }
  }
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "jwt" {
  name                    = "${var.name}/jwt"
  description             = "JWT signing secret (HS256 until P5 moves to RS256 + JWKS)"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  tags                    = merge(var.tags, { Name = "${var.name}/jwt" })
}

resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id     = aws_secretsmanager_secret.jwt.id
  secret_string = jsonencode({ secret = random_password.jwt_secret.result, algorithm = "HS256" })
}

resource "aws_secretsmanager_secret" "app" {
  for_each = local.placeholders

  name                    = "${var.name}/${each.key}"
  description             = each.value.description
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  tags                    = merge(var.tags, { Name = "${var.name}/${each.key}" })
}

resource "aws_secretsmanager_secret_version" "app" {
  for_each = local.placeholders

  secret_id     = aws_secretsmanager_secret.app[each.key].id
  secret_string = jsonencode({ for k in each.value.keys : k => "SET_ME" })

  lifecycle {
    # Real values are set outside Terraform; never overwrite them.
    ignore_changes = [secret_string]
  }
}
