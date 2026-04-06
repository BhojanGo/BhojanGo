"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { RestaurantCard } from "@/components/restaurant/RestaurantCard";
import type { Restaurant } from "@bhojango/types";

const CUISINE_TYPES = [
  "All", "Indian", "Chinese", "Italian", "Mexican", "Thai",
  "American", "Japanese", "Mediterranean", "Fast Food",
];

const SORT_OPTIONS = [
  { value: "rating", label: "Rating" },
  { value: "delivery_time", label: "Delivery Time" },
  { value: "delivery_fee", label: "Delivery Fee" },
];

export default function RestaurantsPage() {
  const t = useTranslations("restaurant");
  const tCommon = useTranslations("common");
  const searchParams = useSearchParams();

  const [cuisine, setCuisine] = useState("All");
  const [sortBy, setSortBy] = useState("rating");
  const [vegOnly, setVegOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") ?? "");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["restaurants", { cuisine, sortBy, vegOnly, searchQuery }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (cuisine !== "All") params.set("cuisine_type", cuisine.toLowerCase());
      if (vegOnly) params.set("is_veg", "true");
      if (searchQuery) params.set("q", searchQuery);
      params.set("sort_by", sortBy);
      params.set("limit", "24");
      const { data } = await api.get(`/restaurant/restaurants?${params.toString()}`);
      return data as { items: Restaurant[]; total: number };
    },
    staleTime: 60_000,
  });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Search bar */}
      <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-7xl mx-auto">
          <div className="flex gap-3 items-center">
            <div className="flex-1 relative">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={tCommon("search")}
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-emerald-500 outline-none bg-white"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Filters row */}
        <div className="flex gap-3 items-center mb-6 overflow-x-auto pb-2 scrollbar-hide">
          {CUISINE_TYPES.map((c) => (
            <button
              key={c}
              onClick={() => setCuisine(c)}
              className={`flex-shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition ${
                cuisine === c
                  ? "bg-emerald-500 text-white"
                  : "bg-white border border-gray-300 text-gray-700 hover:border-emerald-400"
              }`}
            >
              {c}
            </button>
          ))}
          <button
            onClick={() => setVegOnly(!vegOnly)}
            className={`flex-shrink-0 flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium transition ${
              vegOnly
                ? "bg-green-500 text-white"
                : "bg-white border border-gray-300 text-gray-700 hover:border-green-400"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-current" />
            {t("veg")}
          </button>
        </div>

        {/* Results */}
        {isLoading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="bg-white rounded-xl h-64 animate-pulse" />
            ))}
          </div>
        )}

        {isError && (
          <div className="text-center py-20">
            <p className="text-gray-500">Failed to load restaurants. Please try again.</p>
          </div>
        )}

        {data && data.items.length === 0 && (
          <div className="text-center py-20">
            <p className="text-2xl mb-2">🍽️</p>
            <p className="text-gray-500">No restaurants found matching your filters.</p>
          </div>
        )}

        {data && data.items.length > 0 && (
          <>
            <p className="text-sm text-gray-500 mb-4">{data.total} restaurants</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {data.items.map((restaurant) => (
                <RestaurantCard key={restaurant.id} restaurant={restaurant} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
