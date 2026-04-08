# ADR-004: Razorpay for India Payments

## Status
Accepted

## Context
BhojanGo operates in India and USA. Need payment processing that supports UPI, net banking, and Indian regulations.

## Decision
Razorpay for India payments, Stripe for USA payments. Country-based routing at checkout.

## Consequences
Full UPI/net banking support in India, Stripe's superior DX for USA. Two payment integrations to maintain.

## Alternatives Considered
- PayU (less developer-friendly)
- CCAvenue (poor API design)
- Stripe-only (no UPI support in India at launch)
