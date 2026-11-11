# ADR-008: Edge routing (AWS ALB + WAF, no Kong)

## Status
Superseded by ADR-011 (Nov 2026). The decision below replaces the original Kong-based one.

## Context
With three backend deployables (core_api, realtime, worker) instead of seven services, a
separate API gateway adds more than it saves. Kong's JWT plugin also rejected the tokens
core_api issues (no `iss` claim matching its consumer key).

## Decision (Nov 2026)
- **AWS:** an **Application Load Balancer** terminates TLS and routes by path to the
  three ECS services: `/ws/*` and `/api/v1/delivery`, `/api/v1/drivers` to realtime;
  `/api/v1/notifications` to worker; everything else under `/api/v1` to core_api.
  **AWS WAF** on the ALB provides managed rule sets and rate limits. Auth is checked by
  the services (ADR-007), not at the edge. Built in P4.
- **Local:** no gateway. Apps and tests call core_api (:8001), realtime (:8004) and
  worker (:8006) directly. P3 removes Kong from the Docker setup; until then the old
  config in `infra/docker/kong/` stays but is not fixed.

## Original decision
Kong Gateway (DB-less mode) with declarative YAML configuration, in front of seven
microservices.

## Consequences
One less component to run, patch and secure; routing lives in Terraform next to the
services it routes to. Per-route rate limits move to WAF rules and to the services where
they need user context (e.g. OTP limits in identity).

## Alternatives Considered
- Keep Kong (extra service; already broken for our tokens)
- AWS API Gateway (higher latency and cost for WebSockets + REST at our volume)
- Traefik / Nginx as a gateway (another thing to run; ALB covers what we need)
