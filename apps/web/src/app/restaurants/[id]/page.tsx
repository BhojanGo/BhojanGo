"use client";

import { useState } from "react";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useCartStore } from "@/store/cart";
import type { Restaurant, MenuCategory, MenuItem } from "@bhojango/types";

interface CategoryWithItems extends MenuCategory {
  items: MenuItem[];
}

function MenuItemCard({
  item,
  restaurant,
}: {
  item: MenuItem;
  restaurant: Restaurant;
}) {
  const t = useTranslations("restaurant");
  const { addItem } = useCartStore();
  const [added, setAdded] = useState(false);

  function handleAdd() {
    addItem({ id: restaurant.id, name: restaurant.name, slug: restaurant.slug }, item, 1);
    setAdded(true);
    setTimeout(() => setAdded(false), 1000);
  }

  return (
    <div className="flex gap-4 py-4 border-b border-gray-100 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-1">
          <span
            className={`inline-flex w-4 h-4 items-center justify-center rounded-sm border-2 ${
              item.is_veg ? "border-green-500" : "border-red-500"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                item.is_veg ? "bg-green-500" : "bg-red-500"
              }`}
            />
          </span>
          {item.is_bestseller && (
            <span className="text-xs text-emerald-500 font-medium">Bestseller</span>
          )}
        </div>
        <h3 className="font-medium text-gray-900 text-sm">{item.name}</h3>
        <p className="text-sm font-semibold text-gray-900 mt-1">
          {restaurant.currency === "INR" ? "₹" : "$"}
          {item.price}
        </p>
        {item.description && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">{item.description}</p>
        )}
      </div>
      <div className="flex-shrink-0 flex flex-col items-center gap-2">
        {item.image_url && (
          <div className="relative w-24 h-20 rounded-lg overflow-hidden">
            <Image src={item.image_url} alt={item.name} fill className="object-cover" />
          </div>
        )}
        <button
          onClick={handleAdd}
          className={`px-4 py-1 rounded-lg text-sm font-semibold border transition ${
            added
              ? "bg-green-500 border-green-500 text-white"
              : "bg-white border-emerald-500 text-emerald-500 hover:bg-emerald-50"
          }`}
        >
          {added ? "✓" : t("addToCart")}
        </button>
      </div>
    </div>
  );
}

export default function RestaurantPage() {
  const t = useTranslations("restaurant");
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const cart = useCartStore();

  const [activeTab, setActiveTab] = useState<"menu" | "reviews">("menu");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  // Fetch restaurant details by ID (UUID)
  const { data: restaurant, isLoading: isLoadingRestaurant, isError } = useQuery({
    queryKey: ["restaurant", params.id],
    queryFn: async () => {
      const { data } = await api.get(`/restaurant/restaurants/${params.id}`);
      return data as Restaurant;
    },
  });

  // Fetch menu categories separately
  const { data: categories, isLoading: isLoadingMenu } = useQuery({
    queryKey: ["restaurant-menu", params.id],
    queryFn: async () => {
      try {
        const { data } = await api.get(`/restaurant/restaurants/${params.id}/menu`);
        // Handle various response formats
        const cats = data.categories || data.items || data;
        return (Array.isArray(cats) ? cats : []) as CategoryWithItems[];
      } catch {
        return [] as CategoryWithItems[];
      }
    },
    enabled: !!params.id,
  });

  const isLoading = isLoadingRestaurant || isLoadingMenu;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="h-56 bg-gray-200 animate-pulse" />
        <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 bg-white rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !restaurant) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-500 mb-4">Restaurant not found.</p>
          <button onClick={() => router.back()} className="text-emerald-500 hover:underline text-sm">
            Go back
          </button>
        </div>
      </div>
    );
  }

  const menuCategories = categories || [];
  const displayedCategories = activeCategory
    ? menuCategories.filter((c) => c.id === activeCategory)
    : menuCategories;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero */}
      <div className="relative h-48 md:h-64 bg-gray-300">
        {restaurant.cover_url && (
          <Image src={restaurant.cover_url} alt={restaurant.name} fill className="object-cover" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
        <button
          onClick={() => router.back()}
          className="absolute top-4 left-4 w-9 h-9 bg-white/90 rounded-full flex items-center justify-center shadow"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      <div className="max-w-4xl mx-auto px-4">
        {/* Info card */}
        <div className="bg-white rounded-2xl shadow-sm p-5 -mt-8 relative z-10 mb-4">
          <div className="flex items-start gap-3">
            {restaurant.logo_url && (
              <div className="relative w-16 h-16 rounded-xl overflow-hidden flex-shrink-0 border border-gray-100">
                <Image src={restaurant.logo_url} alt={restaurant.name} fill className="object-cover" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-bold text-gray-900">{restaurant.name}</h1>
              <p className="text-sm text-gray-500 mt-0.5">{restaurant.cuisine_types?.join(", ")}</p>
              <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                <span className="flex items-center gap-1">
                  <span className="text-yellow-400">★</span>
                  {restaurant.rating?.toFixed(1)} ({restaurant.review_count})
                </span>
                <span>
                  {t("deliveryTime", {
                    min: restaurant.delivery_time_min ?? 30,
                    max: restaurant.delivery_time_max ?? 45,
                  })}
                </span>
                <span>
                  {restaurant.currency === "INR" ? "₹" : "$"}
                  {restaurant.delivery_fee} {t("deliveryFee").toLowerCase()}
                </span>
              </div>
            </div>
            <span
              className={`text-xs font-medium px-2 py-1 rounded-full ${
                restaurant.is_open
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-600"
              }`}
            >
              {restaurant.is_open ? t("openNow") : t("closed")}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-6 border-b border-gray-200 bg-white px-5">
          {(["menu", "reviews"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 text-sm font-medium border-b-2 transition ${
                activeTab === tab
                  ? "border-emerald-500 text-emerald-500"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t(tab)}
            </button>
          ))}
        </div>

        {activeTab === "menu" && (
          <div className="flex gap-4 py-4">
            {/* Category sidebar */}
            {menuCategories.length > 1 && (
              <div className="hidden md:flex flex-col gap-1 w-40 flex-shrink-0">
                <button
                  onClick={() => setActiveCategory(null)}
                  className={`text-left px-3 py-2 rounded-lg text-sm transition ${
                    !activeCategory ? "bg-emerald-50 text-emerald-700 font-medium" : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  All
                </button>
                {menuCategories.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setActiveCategory(cat.id)}
                    className={`text-left px-3 py-2 rounded-lg text-sm transition ${
                      activeCategory === cat.id
                        ? "bg-emerald-50 text-emerald-700 font-medium"
                        : "text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>
            )}

            {/* Menu items */}
            <div className="flex-1 min-w-0 space-y-6">
              {!menuCategories.length && (
                <p className="text-gray-500 py-8 text-center">{t("noMenu")}</p>
              )}
              {displayedCategories?.map((category) => (
                <div key={category.id} className="bg-white rounded-xl p-4">
                  <h2 className="font-semibold text-gray-900 mb-1">{category.name}</h2>
                  <div>
                    {category.items?.map((item) => (
                      <MenuItemCard key={item.id} item={item} restaurant={restaurant} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "reviews" && (
          <div className="py-6 bg-white rounded-xl mt-4 p-5">
            <p className="text-gray-500 text-sm text-center">Reviews coming soon.</p>
          </div>
        )}
      </div>

      {/* Floating cart button */}
      {cart.restaurantId === restaurant.id && cart.items.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
          <button
            onClick={() => router.push("/cart")}
            className="flex items-center gap-4 bg-emerald-500 text-white px-6 py-3 rounded-full shadow-lg hover:bg-emerald-700 transition"
          >
            <span className="bg-white/20 rounded-full w-7 h-7 flex items-center justify-center text-sm font-bold">
              {cart.getItemCount()}
            </span>
            <span className="font-semibold">View Cart</span>
            <span className="font-semibold">
              {restaurant.currency === "INR" ? "₹" : "$"}
              {cart.getTotal().toFixed(2)}
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
