# ADR-001: Monorepo with Turborepo

## Status
Accepted

## Context
Need to manage 7 services + 3 apps + shared packages. Evaluated polyrepo vs monorepo.

## Decision
Turborepo monorepo with pnpm workspaces. Single repo for all services and apps.

## Consequences
Atomic commits across services, shared CI/CD, easier code sharing. Larger repo size.

## Alternatives Considered
- Polyrepo (too much overhead for small team)
- Nx (heavier tooling)
- Lerna (deprecated)
