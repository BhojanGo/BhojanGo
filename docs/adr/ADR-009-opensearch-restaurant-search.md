# ADR-009: Restaurant search (PostgreSQL, no OpenSearch)

## Status
Superseded by ADR-011 (Nov 2026). The decision below replaces the original OpenSearch-based one.

## Context
Customers search restaurants and dishes within a delivery zone: full-text with typo
tolerance, filters (cuisine, veg, open now), and sorting by distance and rating. The
pilot covers two cities (Hyderabad, Boise), so catalogs are city-scale.

## Decision (Nov 2026)
**Search in PostgreSQL 16 with PostGIS; no OpenSearch.**
- Full-text with `tsvector` columns and GIN indexes (English and Indian-language
  configurations as needed), plus `pg_trgm` for typo-tolerant and prefix matching.
- Distance filtering and sorting with PostGIS on restaurant locations and zone polygons
  (markets, P6).
- One source of truth, so no index sync. The catalog module owns the search query
  behind its `service`.

P4 removes OpenSearch from Terraform; the catalog search moves to Postgres. The
OpenSearch code path in `core_api/modules/catalog` stays until then.

## Original decision
AWS OpenSearch for restaurant and menu item search with geo_distance queries.

## Consequences
No cluster to run or pay for, no sync jobs, transactional consistency with the menu.
Relevance tuning is more manual than in a search engine; if catalogs outgrow Postgres
(many cities, heavy autocomplete), revisit with a dedicated engine behind the same
catalog service interface.

## Alternatives Considered
- Keep AWS OpenSearch (cost and index sync for a two-city pilot)
- Algolia / Typesense (another vendor and data copy)
- Elasticsearch self-hosted (operational burden)
