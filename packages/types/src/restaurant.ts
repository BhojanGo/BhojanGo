// ─── Restaurant & Menu Types ──────────────────────────────────────────────────

import type { Country, Currency } from "./user";

export type CuisineType =
  | "indian"
  | "chinese"
  | "italian"
  | "mexican"
  | "american"
  | "thai"
  | "japanese"
  | "mediterranean"
  | "fast_food"
  | "pizza"
  | "burgers"
  | "sushi"
  | "biryani"
  | "south_indian"
  | "north_indian"
  | "street_food"
  | "healthy"
  | "desserts"
  | "beverages"
  | "other";

export type RestaurantStatus = "active" | "inactive" | "pending_approval" | "suspended";

export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface Address {
  street: string;
  city: string;
  state: string;
  zip: string;
  country: Country;
  lat?: number;
  lng?: number;
  landmark?: string;
}

export interface Restaurant {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  description: string;
  cuisine_types: CuisineType[];
  logo_url: string | null;
  cover_url: string | null;
  address: Address;
  location: GeoPoint;
  rating: number; // 0.0 - 5.0
  review_count: number;
  is_open: boolean;
  opens_at: string | null; // HH:MM
  closes_at: string | null; // HH:MM
  delivery_time_min: number; // minutes
  delivery_time_max: number;
  minimum_order_amount: number;
  delivery_fee: number;
  currency: Currency;
  country: Country;
  city: string;
  status: RestaurantStatus;
  is_active: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface RestaurantCreateInput {
  name: string;
  description: string;
  cuisine_types: CuisineType[];
  address: Address;
  location: GeoPoint;
  delivery_time_min: number;
  delivery_time_max: number;
  minimum_order_amount: number;
  delivery_fee: number;
  currency: Currency;
  country: Country;
  city: string;
  opens_at?: string;
  closes_at?: string;
}

export interface MenuCategory {
  id: string;
  restaurant_id: string;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
}

export interface MenuItemCustomization {
  id: string;
  name: string; // e.g. "Spice Level"
  required: boolean;
  min_selections: number;
  max_selections: number;
  options: MenuItemCustomizationOption[];
}

export interface MenuItemCustomizationOption {
  id: string;
  name: string; // e.g. "Mild", "Medium", "Hot"
  additional_price: number;
}

export type Allergen =
  | "gluten"
  | "dairy"
  | "eggs"
  | "nuts"
  | "peanuts"
  | "soy"
  | "shellfish"
  | "fish"
  | "sesame";

export interface MenuItem {
  id: string;
  restaurant_id: string;
  category_id: string | null;
  name: string;
  description: string;
  price: number;
  image_url: string | null;
  category: string;
  is_veg: boolean;
  is_vegan: boolean;
  is_available: boolean;
  is_bestseller: boolean;
  allergens: Allergen[];
  customizations: MenuItemCustomization[];
  sort_order: number;
  prep_time_minutes: number;
  calories: number | null;
  created_at: string;
  updated_at: string;
}

export interface MenuItemCreateInput {
  category_id?: string;
  name: string;
  description: string;
  price: number;
  category: string;
  is_veg: boolean;
  is_vegan?: boolean;
  allergens?: Allergen[];
  customizations?: MenuItemCustomization[];
  prep_time_minutes?: number;
  calories?: number;
}

export interface Review {
  id: string;
  restaurant_id: string;
  order_id: string;
  customer_id: string;
  customer_name: string;
  customer_avatar: string | null;
  rating: number; // 1-5
  comment: string | null;
  food_rating: number | null;
  delivery_rating: number | null;
  created_at: string;
}

export interface ReviewCreateInput {
  order_id: string;
  rating: number;
  comment?: string;
  food_rating?: number;
  delivery_rating?: number;
}

export interface RestaurantSearchParams {
  q?: string;
  city?: string;
  cuisine?: CuisineType;
  min_rating?: number;
  max_delivery_fee?: number;
  is_open?: boolean;
  is_veg?: boolean;
  page?: number;
  limit?: number;
  lat?: number;
  lng?: number;
  radius_km?: number;
}
