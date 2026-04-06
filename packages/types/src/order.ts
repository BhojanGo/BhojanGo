// ─── Order Types ──────────────────────────────────────────────────────────────

import type { Address, GeoPoint } from "./restaurant";
import type { Currency } from "./user";

export type OrderStatus =
  | "pending"
  | "confirmed"
  | "preparing"
  | "ready_for_pickup"
  | "picked_up"
  | "delivered"
  | "cancelled";

export type CancellationReason =
  | "customer_cancelled"
  | "restaurant_cancelled"
  | "driver_not_found"
  | "payment_failed"
  | "item_unavailable"
  | "restaurant_closed"
  | "other";

export type PaymentMethodType = "card" | "wallet" | "upi" | "net_banking" | "cash_on_delivery";

export interface OrderItemCustomization {
  customization_id: string;
  customization_name: string;
  option_id: string;
  option_name: string;
  additional_price: number;
}

export interface OrderItem {
  menu_item_id: string;
  name: string;
  price: number;
  quantity: number;
  customizations: OrderItemCustomization[];
  subtotal: number;
  image_url: string | null;
}

export interface Order {
  id: string;
  customer_id: string;
  restaurant_id: string;
  restaurant_name: string;
  driver_id: string | null;
  items: OrderItem[];
  status: OrderStatus;
  subtotal: number;
  delivery_fee: number;
  taxes: number;
  tip: number;
  discount: number;
  total: number;
  currency: Currency;
  delivery_address: Address;
  payment_method: PaymentMethodType;
  payment_intent_id: string | null;
  estimated_delivery_time: string | null; // ISO 8601
  actual_delivery_time: string | null;
  cancellation_reason: CancellationReason | null;
  cancellation_note: string | null;
  special_instructions: string | null;
  promo_code: string | null;
  loyalty_points_earned: number;
  loyalty_points_used: number;
  created_at: string;
  updated_at: string;
}

export interface OrderCreateInput {
  restaurant_id: string;
  items: Array<{
    menu_item_id: string;
    quantity: number;
    customizations?: Array<{
      customization_id: string;
      option_id: string;
    }>;
  }>;
  delivery_address: Address;
  payment_method: PaymentMethodType;
  special_instructions?: string;
  promo_code?: string;
  tip?: number;
  loyalty_points_to_use?: number;
}

export interface OrderStatusUpdateInput {
  status: OrderStatus;
  note?: string;
}

export interface OrderCancelInput {
  reason: CancellationReason;
  note?: string;
}

export interface OrderSummary {
  id: string;
  restaurant_name: string;
  status: OrderStatus;
  total: number;
  currency: Currency;
  item_count: number;
  created_at: string;
  estimated_delivery_time: string | null;
}
