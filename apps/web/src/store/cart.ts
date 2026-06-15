import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { MenuItem, MenuItemCustomization, Restaurant } from "@bhojango/types";

export const CART_STORAGE_KEY = "bhojango-cart-guest";
export const CART_SCHEMA_VERSION = 1;
export const GST_TAX_RATE = 0.05;
export const PLATFORM_FEE_RATE = 0.02;
export const INR_DELIVERY_FEE_THRESHOLD = 200;
export const INR_DELIVERY_FEE_BELOW_THRESHOLD = 50;
export const INR_DELIVERY_FEE_AT_OR_ABOVE_THRESHOLD = 30;
export const DEFAULT_DELIVERY_FEE_USD = 3;

type CartCurrency = "INR" | "USD";

type CartRestaurant = Pick<Restaurant, "id" | "name" | "slug"> &
  Partial<Pick<Restaurant, "currency" | "delivery_fee">>;

export interface CartItem {
  menuItemId: string;
  name: string;
  price: number;
  quantity: number;
  customizations: MenuItemCustomization[];
  imageUrl?: string;
  isVeg: boolean;
}

interface CartState {
  schemaVersion: number;
  updatedAt: string | null;
  restaurantId: string | null;
  restaurantName: string | null;
  restaurantSlug: string | null;
  currency: CartCurrency;
  items: CartItem[];
  deliveryFee: number;
  platformFeeRate: number;
  taxRate: number;
  discountAmount: number;

  addItem: (
    restaurant: CartRestaurant,
    item: MenuItem,
    quantity: number,
    customizations?: MenuItemCustomization[]
  ) => void;
  replaceCartWithItem: (
    restaurant: CartRestaurant,
    item: MenuItem,
    quantity: number,
    customizations?: MenuItemCustomization[]
  ) => void;
  removeItem: (menuItemId: string) => void;
  updateQuantity: (menuItemId: string, quantity: number) => void;
  clearCart: () => void;
  hasRestaurantConflict: (restaurantId: string) => boolean;
  getSubtotal: () => number;
  getDeliveryFee: () => number;
  getPlatformFee: () => number;
  getTax: () => number;
  getDiscount: () => number;
  getGrandTotal: () => number;
  getTotal: () => number;
  getItemCount: () => number;
}

function roundMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

function normaliseCurrency(currency?: string | null): CartCurrency {
  return currency === "INR" ? "INR" : "USD";
}

function defaultDeliveryFee(currency: CartCurrency): number {
  return currency === "INR" ? INR_DELIVERY_FEE_AT_OR_ABOVE_THRESHOLD : DEFAULT_DELIVERY_FEE_USD;
}

function normaliseDeliveryFee(restaurant: CartRestaurant, currency: CartCurrency): number {
  const apiFee = Number(restaurant.delivery_fee);
  if (Number.isFinite(apiFee) && apiFee >= 0) {
    return roundMoney(apiFee);
  }
  return defaultDeliveryFee(currency);
}

function calculateDeliveryFeeForCart(
  currency: CartCurrency,
  subtotal: number,
  storedDeliveryFee: number
): number {
  if (subtotal <= 0) {
    return 0;
  }

  // SPR-03A-FIX2: frontend cart display groundwork follows the agreed INR slab.
  // Backend/source-of-truth fee recomputation remains deferred to SPR-03B.
  if (currency === "INR") {
    return subtotal < INR_DELIVERY_FEE_THRESHOLD
      ? INR_DELIVERY_FEE_BELOW_THRESHOLD
      : INR_DELIVERY_FEE_AT_OR_ABOVE_THRESHOLD;
  }

  return roundMoney(storedDeliveryFee);
}

function withUpdatedAt<T extends object>(state: T): T & { updatedAt: string } {
  return {
    ...state,
    updatedAt: new Date().toISOString(),
  };
}

function buildCartItem(
  item: MenuItem,
  quantity: number,
  customizations: MenuItemCustomization[] = []
): CartItem {
  return {
    menuItemId: item.id,
    name: item.name,
    price: Number(item.price) || 0,
    quantity: Math.max(1, quantity),
    customizations,
    imageUrl: item.image_url ?? undefined,
    isVeg: Boolean(item.is_veg),
  };
}

const emptyCartState = {
  restaurantId: null,
  restaurantName: null,
  restaurantSlug: null,
  currency: "INR" as CartCurrency,
  items: [] as CartItem[],
  deliveryFee: 0,
  discountAmount: 0,
};

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      schemaVersion: CART_SCHEMA_VERSION,
      updatedAt: null,
      ...emptyCartState,
      platformFeeRate: PLATFORM_FEE_RATE,
      taxRate: GST_TAX_RATE,

      hasRestaurantConflict: (restaurantId) => {
        const state = get();
        return Boolean(
          state.restaurantId &&
            state.items.length > 0 &&
            state.restaurantId !== restaurantId
        );
      },

      addItem: (restaurant, item, quantity, customizations = []) => {
        const state = get();

        if (state.hasRestaurantConflict(restaurant.id)) {
          throw new Error("CART_RESTAURANT_CONFLICT");
        }

        const currency = normaliseCurrency(restaurant.currency ?? state.currency);
        const deliveryFee =
          state.items.length === 0 ? normaliseDeliveryFee(restaurant, currency) : state.deliveryFee;
        const existing = state.items.find((i) => i.menuItemId === item.id);

        if (existing) {
          set(
            withUpdatedAt({
              items: state.items.map((i) =>
                i.menuItemId === item.id
                  ? { ...i, quantity: i.quantity + Math.max(1, quantity) }
                  : i
              ),
              currency,
              deliveryFee,
            })
          );
          return;
        }

        set(
          withUpdatedAt({
            restaurantId: restaurant.id,
            restaurantName: restaurant.name,
            restaurantSlug: restaurant.slug,
            currency,
            deliveryFee,
            items: [...state.items, buildCartItem(item, quantity, customizations)],
          })
        );
      },

      replaceCartWithItem: (restaurant, item, quantity, customizations = []) => {
        const currency = normaliseCurrency(restaurant.currency);
        set(
          withUpdatedAt({
            restaurantId: restaurant.id,
            restaurantName: restaurant.name,
            restaurantSlug: restaurant.slug,
            currency,
            deliveryFee: normaliseDeliveryFee(restaurant, currency),
            discountAmount: 0,
            items: [buildCartItem(item, quantity, customizations)],
          })
        );
      },

      removeItem: (menuItemId) => {
        const items = get().items.filter((i) => i.menuItemId !== menuItemId);
        if (items.length === 0) {
          set(withUpdatedAt({ ...emptyCartState }));
          return;
        }
        set(withUpdatedAt({ items }));
      },

      updateQuantity: (menuItemId, quantity) => {
        if (quantity <= 0) {
          get().removeItem(menuItemId);
          return;
        }
        set(
          withUpdatedAt({
            items: get().items.map((i) =>
              i.menuItemId === menuItemId ? { ...i, quantity } : i
            ),
          })
        );
      },

      clearCart: () => set(withUpdatedAt({ ...emptyCartState })),

      getSubtotal: () =>
        roundMoney(get().items.reduce((sum, item) => sum + item.price * item.quantity, 0)),

      getDeliveryFee: () =>
        calculateDeliveryFeeForCart(get().currency, get().getSubtotal(), get().deliveryFee),

      getPlatformFee: () => roundMoney(get().getSubtotal() * get().platformFeeRate),

      getTax: () => roundMoney(get().getSubtotal() * get().taxRate),

      getDiscount: () => roundMoney(get().discountAmount),

      getGrandTotal: () => {
        const state = get();
        return roundMoney(
          Math.max(
            0,
            state.getSubtotal() +
              state.getDeliveryFee() +
              state.getPlatformFee() +
              state.getTax() -
              state.getDiscount()
          )
        );
      },

      getTotal: () => get().getGrandTotal(),

      getItemCount: () =>
        get().items.reduce((sum, item) => sum + item.quantity, 0),
    }),
    {
      name: CART_STORAGE_KEY,
      version: CART_SCHEMA_VERSION,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        schemaVersion: CART_SCHEMA_VERSION,
        updatedAt: state.updatedAt,
        restaurantId: state.restaurantId,
        restaurantName: state.restaurantName,
        restaurantSlug: state.restaurantSlug,
        currency: state.currency,
        items: state.items,
        deliveryFee: state.deliveryFee,
        discountAmount: state.discountAmount,
      }),
      migrate: (persistedState) => {
        const state = (persistedState ?? {}) as Partial<CartState>;
        return {
          ...state,
          schemaVersion: CART_SCHEMA_VERSION,
          updatedAt: state.updatedAt ?? new Date().toISOString(),
          currency: normaliseCurrency(state.currency),
          deliveryFee:
            typeof state.deliveryFee === "number" && Number.isFinite(state.deliveryFee)
              ? state.deliveryFee
              : 0,
          discountAmount: 0,
          platformFeeRate: PLATFORM_FEE_RATE,
          taxRate: GST_TAX_RATE,
        };
      },
    }
  )
);
