# ADR-003: DynamoDB for Driver Locations

## Status
Accepted

## Context
Driver GPS updates every 10 seconds for hundreds of active drivers. Need low-latency writes and TTL.

## Decision
DynamoDB for real-time driver location storage with TTL for automatic cleanup.

## Consequences
Sub-millisecond writes, automatic scaling, built-in TTL. Higher cost than Redis for this use case.

## Alternatives Considered
- Redis GEO (volatile, no persistence)
- PostGIS (too slow for write-heavy GPS data)
- MongoDB (operational overhead)
