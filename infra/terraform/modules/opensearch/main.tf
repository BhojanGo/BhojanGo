# ──────────────────────────────────────────────
# OpenSearch — full-text search for restaurants & menus
# ──────────────────────────────────────────────

resource "aws_opensearch_domain" "main" {
  domain_name    = var.name
  engine_version = "OpenSearch_2.14"

  cluster_config {
    instance_type            = var.environment == "prod" ? "r6g.large.search" : "t3.medium.search"
    instance_count           = var.environment == "prod" ? 2 : 1
    zone_awareness_enabled   = var.environment == "prod"
    dedicated_master_enabled = false

    dynamic "zone_awareness_config" {
      for_each = var.environment == "prod" ? [1] : []
      content {
        availability_zone_count = 2
      }
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_size = var.environment == "prod" ? 100 : 20
    volume_type = "gp3"
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-PFS-2023-10"
  }

  vpc_options {
    subnet_ids         = var.environment == "prod" ? var.subnet_ids : [var.subnet_ids[0]]
    security_group_ids = [var.security_group_id]
  }

  advanced_options = {
    "rest.action.multi.allow_explicit_index" = "true"
  }

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "*" }
      Action    = "es:*"
      Resource  = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${var.name}/*"
    }]
  })

  tags = merge(var.tags, { Name = "${var.name}-opensearch" })
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
