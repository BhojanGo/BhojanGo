import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { MenuItem, MenuItemCustomization, Restaurant } from "@bhojango/types";

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
  restaurantId: string | null;
  restaurantName: string | null;
  restaurantSlug: string | null;
  items: CartItem[];
  deliveryFee: number;
  taxRate: number;

  addItem: (restaurant: Pick<Restaurant, "id" | "name" | "slug">, item: MenuItem, quantity: number, customizations?: MenuItemCustomization[]) => void;
  removeItem: (menuItemId: string) => void;
  updateQuantity: (menuItemId: string, quantity: number) => void;
  clearCart: () => void;
  getSubtotal: () => number;
  getTax: () => number;
  getTotal: () => number;
  getItemCount: () => number;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      restaurantId: null,
      restaurantName: null,
      restaurantSlug: null,
      items: [],
      deliveryFee: 0,
      taxRate: 0.1, // 10% default

      addItem: (restaurant, item, quantity, customizations = []) => {
        const { restaurantId, items } = get();

        // If adding from a different restaurant, clear cart first
        if (restaurantId && restaurantId !== restaurant.id) {
          set({
            restaurantId: restaurant.id,
            restaurantName: restaurant.name,
            restaurantSlug: restaurant.slug,
            items: [],
            deliveryFee: 0,
          });
        }

        const existing = items.find((i) => i.menuItemId === item.id);
        if (existing) {
          set({
            items: items.map((i) =>
              i.menuItemId === item.id
                ? { ...i, quantity: i.quantity + quantity }
                : i
            ),
          });
        } else {
          set({
            restaurantId: restaurant.id,
            restaurantName: restaurant.name,
            restaurantSlug: restaurant.slug,
            items: [
              ...items,
              {
                menuItemId: item.id,
                name: item.name,
                price: item.price,
                quantity,
                customizations,
                imageUrl: item.image_url ?? undefined,
                isVeg: item.is_veg,
              },
            ],
          });
        }
      },

      removeItem: (menuItemId) => {
        const items = get().items.filter((i) => i.menuItemId !== menuItemId);
        if (items.length === 0) {
          set({ items: [], restaurantId: null, restaurantName: null, restaurantSlug: null });
        } else {
          set({ items });
        }
      },

      updateQuantity: (menuItemId, quantity) => {
        if (quantity <= 0) {
          get().removeItem(menuItemId);
          return;
        }
        set({
          items: get().items.map((i) =>
            i.menuItemId === menuItemId ? { ...i, quantity } : i
          ),
        });
      },

      clearCart: () =>
        set({
          restaurantId: null,
          restaurantName: null,
          restaurantSlug: null,
          items: [],
          deliveryFee: 0,
        }),

      getSubtotal: () =>
        get().items.reduce((sum, item) => sum + item.price * item.quantity, 0),

      getTax: () => {
        const subtotal = get().getSubtotal();
        return Math.round(subtotal * get().taxRate * 100) / 100;
      },

      getTotal: () => {
        const { getSubtotal, getTax, deliveryFee } = get();
        return getSubtotal() + getTax() + deliveryFee;
      },

      getItemCount: () =>
        get().items.reduce((sum, item) => sum + item.quantity, 0),
    }),
    {
      name: "bhojango-cart",
      partialize: (state) => ({
        restaurantId: state.restaurantId,
        restaurantName: state.restaurantName,
        restaurantSlug: state.restaurantSlug,
        items: state.items,
        deliveryFee: state.deliveryFee,
      }),
    }
  )
);
