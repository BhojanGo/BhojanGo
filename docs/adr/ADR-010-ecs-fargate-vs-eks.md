# ADR-010: ECS Fargate over EKS

## Status
Accepted

## Context
Need container orchestration for 7 microservices with auto-scaling and rolling deployments.

## Decision
ECS Fargate for all services — serverless containers without managing EC2 instances.

## Consequences
No cluster management, pay-per-use, integrated with ALB and CloudWatch. Less flexibility than Kubernetes.

## Alternatives Considered
- EKS (operational overhead for small team)
- EC2 with Docker Compose (not production-grade)
- Lambda (not suitable for long-running services)
