# ADR-008: Kong API Gateway

## Status
Accepted

## Context
Need API gateway for routing, rate limiting, JWT validation, and CORS across 7 microservices.

## Decision
Kong Gateway (DB-less mode) with declarative YAML configuration.

## Consequences
Centralized routing and security, plugin ecosystem, no database dependency. Additional infrastructure component.

## Alternatives Considered
- AWS API Gateway (higher latency, less flexible)
- Traefik (less mature plugin ecosystem)
- Nginx (manual config)
