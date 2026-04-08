# ADR-009: OpenSearch for Restaurant Search

## Status
Accepted

## Context
Restaurant search needs full-text search, fuzzy matching, geo-distance sorting, and faceted filtering.

## Decision
AWS OpenSearch for restaurant and menu item search with geo_distance queries.

## Consequences
Fast full-text search, geo-spatial queries, auto-suggest. Requires index sync from PostgreSQL.

## Alternatives Considered
- PostgreSQL FTS (limited fuzzy matching, no geo-distance sort)
- Algolia (expensive)
- Elasticsearch self-hosted (operational burden)
