import { create } from "zustand";

import type { MenuItem, Restaurant } from "@bhojango/types";

interface CartItem {
  menuItemId: string;
  name: string;
  price: number;
  quantity: number;
  isVeg: boolean;
}

interface CartState {
  restaurantId: string | null;
  restaurantName: string | null;
  items: CartItem[];
  deliveryFee: number;

  addItem: (restaurant: Pick<Restaurant, "id" | "name">, item: MenuItem, quantity?: number) => void;
  removeItem: (menuItemId: string) => void;
  updateQuantity: (menuItemId: string, quantity: number) => void;
  clearCart: () => void;
  getSubtotal: () => number;
  getTotal: () => number;
  getItemCount: () => number;
}

export const useCartStore = create<CartState>()((set, get) => ({
  restaurantId: null,
  restaurantName: null,
  items: [],
  deliveryFee: 0,

  addItem: (restaurant, item, quantity = 1) => {
    const { restaurantId, items } = get();
    if (restaurantId && restaurantId !== restaurant.id) {
      set({ restaurantId: restaurant.id, restaurantName: restaurant.name, items: [], deliveryFee: 0 });
    }
    const existing = items.find((i) => i.menuItemId === item.id);
    if (existing) {
      set({ items: items.map((i) => i.menuItemId === item.id ? { ...i, quantity: i.quantity + quantity } : i) });
    } else {
      set({
        restaurantId: restaurant.id,
        restaurantName: restaurant.name,
        items: [...items, { menuItemId: item.id, name: item.name, price: item.price, quantity, isVeg: item.is_veg }],
      });
    }
  },

  removeItem: (menuItemId) => {
    const items = get().items.filter((i) => i.menuItemId !== menuItemId);
    if (items.length === 0) {
      set({ items: [], restaurantId: null, restaurantName: null });
    } else {
      set({ items });
    }
  },

  updateQuantity: (menuItemId, quantity) => {
    if (quantity <= 0) { get().removeItem(menuItemId); return; }
    set({ items: get().items.map((i) => i.menuItemId === menuItemId ? { ...i, quantity } : i) });
  },

  clearCart: () => set({ restaurantId: null, restaurantName: null, items: [], deliveryFee: 0 }),

  getSubtotal: () => get().items.reduce((s, i) => s + i.price * i.quantity, 0),
  getTotal: () => get().getSubtotal() + get().deliveryFee,
  getItemCount: () => get().items.reduce((s, i) => s + i.quantity, 0),
}));
