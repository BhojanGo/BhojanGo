# ADR-002: FastAPI with Python

## Status
Accepted

## Context
Need async-capable backend framework for microservices handling food delivery operations.

## Decision
FastAPI with async SQLAlchemy for all Python services.

## Consequences
High performance async I/O, auto-generated OpenAPI docs, strong typing with Pydantic.

## Alternatives Considered
- Django REST (too heavy, sync by default)
- Flask (no built-in async, less structured)
- Express.js (team expertise is Python)
