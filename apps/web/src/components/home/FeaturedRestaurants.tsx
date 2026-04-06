"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Spinner } from "@bhojango/ui";
import type { Restaurant } from "@bhojango/types";

import { RestaurantCard } from "@/components/restaurant/RestaurantCard";
import { api } from "@/lib/api";

export function FeaturedRestaurants() {
  const { data, isLoading } = useQuery({
    queryKey: ["restaurants", "featured"],
    queryFn: () => api.get<{ items: Restaurant[] }>("/restaurant/restaurants?limit=6").then((r) => r.data),
  });

  return (
    <section className="bg-gray-50 py-16 dark:bg-gray-950">
      <div className="mx-auto max-w-6xl px-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Featured restaurants</h2>
            <p className="mt-1 text-gray-500 dark:text-gray-400">Top-rated picks in your area</p>
          </div>
          <Link href="/restaurants" className="text-sm font-medium text-brand-500 hover:text-brand-600">
            View all →
          </Link>
        </div>

        {isLoading ? (
          <div className="mt-8 flex justify-center">
            <Spinner size="lg" />
          </div>
        ) : (
          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {data?.items?.map((restaurant) => (
              <RestaurantCard key={restaurant.id} restaurant={restaurant} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
