// ─── Payment Types ────────────────────────────────────────────────────────────

import type { Currency } from "./user";

export type PaymentProvider = "stripe" | "razorpay" | "wallet";

export type PaymentStatus =
  | "pending"
  | "processing"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "refunded"
  | "partially_refunded";

export interface PaymentMethod {
  id: string;
  user_id: string;
  provider: PaymentProvider;
  type: "card" | "upi" | "net_banking" | "wallet";
  last_four: string | null;
  brand: string | null; // visa, mastercard, rupay etc.
  exp_month: number | null;
  exp_year: number | null;
  is_default: boolean;
  provider_payment_method_id: string; // stripe/razorpay method id
  created_at: string;
}

export interface PaymentIntent {
  id: string;
  order_id: string;
  user_id: string;
  provider: PaymentProvider;
  provider_payment_id: string; // stripe PaymentIntent id or razorpay order id
  amount: number; // in smallest currency unit (cents/paise)
  currency: Currency;
  status: PaymentStatus;
  idempotency_key: string;
  metadata: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface PaymentInitiateInput {
  order_id: string;
  payment_method_type: "card" | "upi" | "net_banking" | "wallet";
  payment_method_id?: string; // for saved cards
  country: string; // "US" → Stripe, "IN" → Razorpay
  tip?: number;
}

export interface PaymentInitiateResponse {
  payment_intent_id: string;
  provider: PaymentProvider;
  client_secret: string | null; // Stripe
  razorpay_order_id: string | null; // Razorpay
  amount: number;
  currency: Currency;
}

export interface WalletBalance {
  user_id: string;
  balance: number;
  currency: Currency;
  updated_at: string;
}

export interface WalletTransaction {
  id: string;
  user_id: string;
  type: "credit" | "debit";
  amount: number;
  currency: Currency;
  balance_after: number;
  description: string;
  reference_id: string | null; // order_id or topup_id
  reference_type: "order" | "topup" | "refund" | "adjustment" | null;
  created_at: string;
}

export interface WalletTopupInput {
  amount: number;
  currency: Currency;
  payment_method_id: string;
}

export interface RefundInput {
  order_id: string;
  amount?: number; // partial refund if specified
  reason: string;
  refund_to: "original_payment" | "wallet";
}

export interface RefundResponse {
  refund_id: string;
  order_id: string;
  amount: number;
  currency: Currency;
  status: "pending" | "succeeded" | "failed";
  refund_to: "original_payment" | "wallet";
  created_at: string;
}
