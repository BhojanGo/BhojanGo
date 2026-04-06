// ─── Domain Events (SNS/SQS typed union) ─────────────────────────────────────
// Every event published to SNS follows this shape.

import type { DriverLocation } from "./delivery";
import type { Order, OrderStatus } from "./order";
import type { PaymentIntent, PaymentStatus } from "./payment";

export interface BaseEvent {
  event_id: string; // UUID v4
  event_version: "1.0";
  timestamp: string; // ISO 8601
  source_service: string;
  correlation_id: string; // trace id
}

// ── Order Events ──────────────────────────────────────────────────────────────

export interface OrderCreatedEvent extends BaseEvent {
  event_type: "order.created";
  payload: {
    order_id: string;
    customer_id: string;
    restaurant_id: string;
    total: number;
    currency: string;
    payment_method: string;
  };
}

export interface OrderConfirmedEvent extends BaseEvent {
  event_type: "order.confirmed";
  payload: {
    order_id: string;
    restaurant_id: string;
    estimated_prep_minutes: number;
  };
}

export interface OrderStatusChangedEvent extends BaseEvent {
  event_type: "order.status_changed";
  payload: {
    order_id: string;
    customer_id: string;
    driver_id: string | null;
    restaurant_id: string;
    previous_status: OrderStatus;
    new_status: OrderStatus;
    note: string | null;
  };
}

export interface OrderCancelledEvent extends BaseEvent {
  event_type: "order.cancelled";
  payload: {
    order_id: string;
    customer_id: string;
    restaurant_id: string;
    reason: string;
    refund_amount: number;
    currency: string;
  };
}

// ── Payment Events ────────────────────────────────────────────────────────────

export interface PaymentSucceededEvent extends BaseEvent {
  event_type: "payment.succeeded";
  payload: {
    payment_intent_id: string;
    order_id: string;
    user_id: string;
    amount: number;
    currency: string;
    provider: string;
  };
}

export interface PaymentFailedEvent extends BaseEvent {
  event_type: "payment.failed";
  payload: {
    payment_intent_id: string;
    order_id: string;
    user_id: string;
    failure_reason: string;
    provider: string;
  };
}

// ── Delivery Events ───────────────────────────────────────────────────────────

export interface DriverLocationUpdatedEvent extends BaseEvent {
  event_type: "driver.location_updated";
  payload: DriverLocation;
}

export interface DriverAssignedEvent extends BaseEvent {
  event_type: "driver.assigned";
  payload: {
    order_id: string;
    driver_id: string;
    driver_name: string;
    driver_phone: string;
    driver_avatar: string | null;
    estimated_pickup_minutes: number;
  };
}

// ── User Events ───────────────────────────────────────────────────────────────

export interface UserRegisteredEvent extends BaseEvent {
  event_type: "user.registered";
  payload: {
    user_id: string;
    email: string;
    full_name: string;
    country: string;
  };
}

// ── Union Type ────────────────────────────────────────────────────────────────

export type DomainEvent =
  | OrderCreatedEvent
  | OrderConfirmedEvent
  | OrderStatusChangedEvent
  | OrderCancelledEvent
  | PaymentSucceededEvent
  | PaymentFailedEvent
  | DriverLocationUpdatedEvent
  | DriverAssignedEvent
  | UserRegisteredEvent;

export type DomainEventType = DomainEvent["event_type"];
