# ADR-002: FastAPI with Python

## Status
Accepted. Amended by ADR-011 (Nov 2026).

## Context
Need async-capable backend framework for the food delivery platform.

## Decision (amended Nov 2026)
FastAPI on **Python 3.12** with async SQLAlchemy 2, Pydantic 2 and Alembic, managed as
**one uv project** (`backend/pyproject.toml`, `backend/uv.lock`). The backend is three
deployables instead of seven microservices:

- **core_api** (:8001): a modular monolith; modules `identity`, `catalog`, `orders`,
  `payments`, later `markets`, `rules`, `pricing`, `promotions`, `finance`, `audit`.
  Every module has `api/`, `service/`, `repository/`, `models/` and `schemas/`; modules
  talk to each other only through their `service`.
- **realtime** (:8004): rider GPS, tracking WebSocket, dispatch, ETA.
- **worker** (:8006): outbox relay, notifications, payouts, batching.

Shared code (config, DB session, Redis, auth, events, logging) lives in `backend/shared`;
one Alembic history lives in `backend/migrations`. Pinned versions: ADR-011.

## Original decision
FastAPI with async SQLAlchemy for all Python services (one service per domain).

## Consequences
High-performance async I/O, auto-generated OpenAPI (the source for
`packages/api-client` in P16/P17), strong typing with Pydantic. Fewer deployables mean
fewer network hops, one migration history and simpler local setup; module boundaries
are kept by code structure and an import-linter check, not by the network.

## Alternatives Considered
- Django REST (too heavy, sync by default)
- Flask (no built-in async, less structured)
- Express.js (team expertise is Python)
- Keep seven microservices (operational cost too high for a two-city pilot)
