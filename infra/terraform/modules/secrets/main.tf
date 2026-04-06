# ──────────────────────────────────────────────
# Secrets Manager — all application secrets
# ──────────────────────────────────────────────

locals {
  secrets = {
    jwt = {
      name        = "${var.name}/jwt"
      description = "JWT signing keys"
      value = jsonencode({
        secret    = random_password.jwt_secret.result
        algorithm = "HS256"
      })
    }
    stripe = {
      name        = "${var.name}/stripe"
      description = "Stripe API keys"
      value = jsonencode({
        secret_key     = var.stripe_secret_key
        webhook_secret = var.stripe_webhook_secret
      })
    }
    razorpay = {
      name        = "${var.name}/razorpay"
      description = "Razorpay API keys"
      value = jsonencode({
        key_id     = var.razorpay_key_id
        key_secret = var.razorpay_key_secret
      })
    }
    twilio = {
      name        = "${var.name}/twilio"
      description = "Twilio API credentials"
      value = jsonencode({
        account_sid = var.twilio_account_sid
        auth_token  = var.twilio_auth_token
        from_number = var.twilio_from_number
      })
    }
    sendgrid = {
      name        = "${var.name}/sendgrid"
      description = "SendGrid API key"
      value = jsonencode({
        api_key = var.sendgrid_api_key
      })
    }
    firebase = {
      name        = "${var.name}/firebase"
      description = "Firebase FCM credentials"
      value = jsonencode({
        project_id      = var.firebase_project_id
        credentials_json = var.firebase_credentials_json
      })
    }
  }
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "secrets" {
  for_each = local.secrets

  name                    = each.value.name
  description             = each.value.description
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  tags                    = merge(var.tags, { Name = each.value.name })
}

resource "aws_secretsmanager_secret_version" "secrets" {
  for_each = local.secrets

  secret_id     = aws_secretsmanager_secret.secrets[each.key].id
  secret_string = each.value.value
}
