# ADR-007: Authentication (custom RS256 + JWKS, no Cognito)

## Status
Superseded by ADR-011 (Nov 2026). The decision below replaces the original Cognito-based one.

## Context
Customers, riders, partners and admins sign in on three Expo apps and two web apps in
the US and India: phone OTP (with DLT-registered templates in India), Sign in with Apple
and Google, and scoped admin roles per country, state or city.

## Decision (Nov 2026)
**Custom auth in `core_api/modules/identity`; no AWS Cognito.**
- Access tokens are **RS256 JWTs**; public keys are published at a **JWKS** endpoint so
  core_api, realtime, worker and the apps verify without sharing a secret. Keys rotate
  by `kid`.
- Refresh tokens are opaque, stored server-side (Redis/Postgres), rotated on use and
  revocable.
- Phone OTP via Twilio (US) and MSG91 (India); Sign in with Apple and Google via their
  ID tokens, verified server-side.
- Admin roles and scopes (super admin, country manager, city ops, support, finance,
  viewer) are claims checked by core_api.

Built in P5. Until then, tokens are HS256 with a shared `JWT_SECRET`, verified by
`backend/shared/auth.py`.

## Original decision
Custom JWT auth service with bcrypt + Redis token storage. AWS Cognito for social
identity federation in production.

## Consequences
No per-user vendor cost and no lock-in; one auth model for every app and market. We
own key management, rotation and revocation, and the OTP abuse limits.

## Alternatives Considered
- AWS Cognito (phone OTP with Indian DLT templates and per-market admin scopes fit poorly)
- Auth0 / Clerk (expensive at scale)
- Supabase Auth (vendor lock-in)
- Firebase Auth (limited customization)
