// ─── Delivery & Driver Types ──────────────────────────────────────────────────

import type { GeoPoint } from "./restaurant";

export type DriverStatus = "offline" | "available" | "busy";

export interface Driver {
  id: string;
  user_id: string;
  full_name: string;
  phone: string;
  avatar_url: string | null;
  vehicle_type: "bicycle" | "motorcycle" | "car" | "scooter";
  vehicle_plate: string | null;
  rating: number;
  total_deliveries: number;
  status: DriverStatus;
  current_location: GeoPoint | null;
  is_active: boolean;
  created_at: string;
}

export interface DriverLocation {
  driver_id: string;
  order_id: string | null;
  location: GeoPoint;
  heading: number | null; // degrees 0-360
  speed: number | null; // km/h
  accuracy: number | null; // meters
  timestamp: string; // ISO 8601
}

export interface DeliveryAssignment {
  id: string;
  order_id: string;
  driver_id: string;
  assigned_at: string;
  picked_up_at: string | null;
  delivered_at: string | null;
  distance_km: number | null;
  duration_minutes: number | null;
}

export interface EtaResponse {
  order_id: string;
  driver_location: GeoPoint | null;
  restaurant_location: GeoPoint;
  delivery_location: GeoPoint;
  estimated_pickup_minutes: number | null;
  estimated_delivery_minutes: number | null;
  estimated_delivery_time: string | null; // ISO 8601
  route_polyline: string | null; // encoded polyline
}

export interface DeliveryHistoryRecord {
  pk: string; // order_id
  sk: string; // timestamp
  driver_id: string;
  location: GeoPoint;
  event_type: "location_update" | "pickup" | "delivery" | "assigned";
  metadata: Record<string, string | number | boolean>;
}

export interface WebSocketLocationMessage {
  type: "location_update" | "status_change" | "eta_update" | "error";
  payload: DriverLocation | { status: string } | EtaResponse | { message: string };
  timestamp: string;
}

export interface DriverLocationUpdateInput {
  lat: number;
  lng: number;
  heading?: number;
  speed?: number;
  accuracy?: number;
}
