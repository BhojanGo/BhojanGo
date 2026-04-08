# ADR-007: Cognito Auth with Custom JWT

## Status
Accepted

## Context
Need user authentication with social login (Google, Apple), phone OTP, and JWT token management.

## Decision
Custom JWT auth service with bcrypt + Redis token storage. AWS Cognito for social identity federation in production.

## Consequences
Full control over auth flow, Redis-backed token revocation, social login via Cognito hosted UI.

## Alternatives Considered
- Auth0 (expensive at scale)
- Supabase Auth (vendor lock-in)
- Firebase Auth (limited customization)
