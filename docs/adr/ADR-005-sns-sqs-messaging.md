# ADR-005: SNS/SQS for Messaging

## Status
Accepted

## Context
Microservices need async event-driven communication for order lifecycle, payments, notifications.

## Decision
AWS SNS for pub/sub topics, SQS for durable queues with DLQ for failed messages.

## Consequences
Managed service, automatic scaling, DLQ for debugging. AWS lock-in, LocalStack needed for local dev.

## Alternatives Considered
- Kafka (operational overhead for small team)
- RabbitMQ (self-managed)
- EventBridge (less flexible routing)
