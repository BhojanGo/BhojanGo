// ─── Notification Types ───────────────────────────────────────────────────────

export type NotificationType =
  | "order_created"
  | "order_confirmed"
  | "order_preparing"
  | "order_ready"
  | "order_picked_up"
  | "order_delivered"
  | "order_cancelled"
  | "payment_succeeded"
  | "payment_failed"
  | "driver_assigned"
  | "promo_offer"
  | "system";

export type NotificationChannel = "push" | "sms" | "email" | "in_app";

export interface Notification {
  id: string;
  user_id: string;
  type: NotificationType;
  channel: NotificationChannel;
  title: string;
  body: string;
  data: Record<string, string> | null; // deep link data
  is_read: boolean;
  sent_at: string | null;
  read_at: string | null;
  created_at: string;
}

export interface DeviceToken {
  id: string;
  user_id: string;
  token: string;
  platform: "ios" | "android" | "web";
  created_at: string;
  updated_at: string;
}

export interface DeviceTokenInput {
  token: string;
  platform: "ios" | "android" | "web";
}

export interface PushNotificationPayload {
  title: string;
  body: string;
  image_url?: string;
  data?: Record<string, string>;
  badge?: number;
  sound?: string;
}
