// ─── API Response Types ───────────────────────────────────────────────────────

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string | null;
  request_id: string;
  timestamp: string;
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details: Record<string, string[]> | null; // validation errors
    request_id: string;
  };
  timestamp: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  meta: PaginationMeta;
  request_id: string;
  timestamp: string;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  service: string;
  version: string;
  uptime_seconds: number;
  checks: {
    database: "ok" | "error";
    redis: "ok" | "error";
    [key: string]: "ok" | "error";
  };
  timestamp: string;
}

// ── HTTP Error Codes ──────────────────────────────────────────────────────────
export type ApiErrorCode =
  | "VALIDATION_ERROR"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "CONFLICT"
  | "RATE_LIMITED"
  | "PAYMENT_FAILED"
  | "ORDER_STATE_INVALID"
  | "RESTAURANT_CLOSED"
  | "ITEM_UNAVAILABLE"
  | "INSUFFICIENT_WALLET_BALANCE"
  | "OTP_EXPIRED"
  | "OTP_INVALID"
  | "EMAIL_ALREADY_EXISTS"
  | "PHONE_ALREADY_EXISTS"
  | "INTERNAL_ERROR";

export interface PresignedUrlResponse {
  upload_url: string;
  file_url: string;
  expires_at: string;
  fields: Record<string, string>; // for multipart form upload
}
