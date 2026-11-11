# ──────────────────────────────────────────────
# One-time bootstrap, run by a person with admin credentials in each AWS
# account (docs/runbooks/aws-setup.md). Uses LOCAL state on purpose: it
# creates what every other stack needs.
#   - S3 bucket for Terraform state + DynamoDB lock table
#   - GitHub OIDC identity provider
#   - per environment: a read-only "plan" role (pull requests) and a
#     "deploy" role (only from the matching GitHub environment)
# No long-lived AWS keys are created.
# ──────────────────────────────────────────────

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "github_repo" {
  description = "owner/name of the GitHub repository allowed to assume the roles."
  type        = string
  default     = "BhojanGo/BhojanGo"
}

variable "environments" {
  description = "Environments hosted in THIS account: [\"staging\"], [\"prod\"], or both for a single-account setup."
  type        = list(string)
  default     = ["staging", "prod"]

  validation {
    condition     = alltrue([for e in var.environments : contains(["staging", "prod"], e)])
    error_message = "environments may contain only staging and prod."
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  state_bucket = "bhojango-tfstate-${local.account_id}"
  lock_table   = "bhojango-terraform-locks"
  # Terraform env name -> GitHub environment name (protection rules live there).
  github_environment = { staging = "staging", prod = "production" }
  tags               = { Project = "BhojanGo", ManagedBy = "Terraform-bootstrap" }
}

# ── Terraform state ──────────────────────────
resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket
  tags   = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "locks" {
  name         = local.lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = local.tags
}

# ── GitHub OIDC ──────────────────────────────
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  tags           = local.tags
}

data "aws_iam_policy_document" "trust" {
  for_each = {
    for pair in setproduct(var.environments, ["plan", "deploy"]) : "${pair[0]}-${pair[1]}" => {
      env  = pair[0]
      kind = pair[1]
    }
  }

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # plan: any pull request in the repo. deploy: only jobs bound to the
    # GitHub environment (which is where approvals are enforced).
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = each.value.kind == "plan" ? ["repo:${var.github_repo}:pull_request"] : [
        "repo:${var.github_repo}:environment:${local.github_environment[each.value.env]}"
      ]
    }
  }
}

resource "aws_iam_role" "github" {
  for_each = data.aws_iam_policy_document.trust

  name                 = "bhojango-${each.key}-github"
  assume_role_policy   = each.value.json
  max_session_duration = 3600
  tags                 = local.tags
}

# Plan roles: read everything, plus read/write the state bucket and lock table
# (terraform plan takes the lock).
resource "aws_iam_role_policy_attachment" "plan_readonly" {
  for_each = { for k, r in aws_iam_role.github : k => r if endswith(k, "-plan") }

  role       = each.value.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "plan_state" {
  for_each = { for k, r in aws_iam_role.github : k => r if endswith(k, "-plan") }

  name = "terraform-state"
  role = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = [aws_dynamodb_table.locks.arn]
      }
    ]
  })
}

# Deploy roles apply Terraform and deploy ECS, so they need broad rights. They
# can only be assumed from a job running in the protected GitHub environment.
resource "aws_iam_role_policy_attachment" "deploy_admin" {
  for_each = { for k, r in aws_iam_role.github : k => r if endswith(k, "-deploy") }

  role       = each.value.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

output "tf_state_bucket" {
  value = aws_s3_bucket.state.bucket
}

output "tf_lock_table" {
  value = aws_dynamodb_table.locks.name
}

output "role_arns" {
  description = "Copy into GitHub repository variables (see the runbook)."
  value       = { for k, r in aws_iam_role.github : k => r.arn }
}
