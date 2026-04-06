// ─── User & Auth Types ────────────────────────────────────────────────────────

export type UserRole = "customer" | "driver" | "restaurant_owner" | "admin" | "super_admin" | "city_manager";

export type UserStatus = "active" | "inactive" | "banned" | "pending_verification";

export type Country = "US" | "IN";

export type Currency = "USD" | "INR";

export type Locale = "en-US" | "en-IN" | "hi-IN";

export interface User {
  id: string;
  email: string;
  phone: string | null;
  full_name: string;
  avatar_url: string | null;
  role: UserRole;
  status: UserStatus;
  is_active: boolean;
  is_verified: boolean;
  is_phone_verified: boolean;
  loyalty_points: number;
  preferred_currency: Currency;
  preferred_locale: Locale;
  country: Country;
  fcm_token: string | null;
  google_id: string | null;
  apple_id: string | null;
  created_at: string; // ISO 8601
  updated_at: string;
}

export interface UserPublic {
  id: string;
  full_name: string;
  avatar_url: string | null;
  loyalty_points: number;
}

export interface UserUpdateInput {
  full_name?: string;
  phone?: string;
  avatar_url?: string;
  preferred_currency?: Currency;
  preferred_locale?: Locale;
}

export interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
  country: Country;
  preferred_currency?: Currency;
  preferred_locale?: Locale;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface OtpSendInput {
  phone: string;
  country: Country;
}

export interface OtpVerifyInput {
  phone: string;
  otp: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number; // seconds
}

export interface JwtPayload {
  sub: string; // user id
  email: string;
  role: UserRole;
  country: Country;
  iat: number;
  exp: number;
}

export interface SocialLoginInput {
  provider: "google" | "apple";
  token: string; // ID token from Google/Apple
  country?: Country;
}

export interface LoyaltyTransaction {
  id: string;
  user_id: string;
  points: number; // positive = earned, negative = redeemed
  reason: string;
  order_id: string | null;
  created_at: string;
}
