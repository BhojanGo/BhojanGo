import Image from "next/image";
import Link from "next/link";

import { Badge, Card } from "@bhojango/ui";
import type { Restaurant } from "@bhojango/types";

interface RestaurantCardProps {
  restaurant: Restaurant;
}

export function RestaurantCard({ restaurant }: RestaurantCardProps) {
  const currencySymbol = restaurant.currency === "INR" ? "₹" : "$";

  return (
    <Link href={`/restaurants/${restaurant.id}`}>
      <Card hover padding="none" className="overflow-hidden">
        {/* Cover image */}
        <div className="relative h-40 w-full bg-gray-200 dark:bg-gray-700">
          {restaurant.cover_url ? (
            <Image
              src={restaurant.cover_url}
              alt={restaurant.name}
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-4xl">🍽️</div>
          )}
          {!restaurant.is_open && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50">
              <span className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-gray-800">
                Closed
              </span>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate font-semibold text-gray-900 dark:text-white">{restaurant.name}</h3>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                {restaurant.cuisine_types.slice(0, 2).join(" • ")}
              </p>
            </div>
            {restaurant.logo_url && (
              <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-lg border border-gray-200">
                <Image src={restaurant.logo_url} alt="" fill className="object-cover" sizes="40px" />
              </div>
            )}
          </div>

          <div className="mt-3 flex items-center gap-3 text-sm text-gray-600 dark:text-gray-300">
            <span className="flex items-center gap-1">
              ⭐ <strong>{restaurant.rating.toFixed(1)}</strong>
              <span className="text-gray-400">({restaurant.review_count})</span>
            </span>
            <span>•</span>
            <span>{restaurant.delivery_time_min}–{restaurant.delivery_time_max} min</span>
            <span>•</span>
            <span>{restaurant.delivery_fee === 0 ? "Free delivery" : `${currencySymbol}${restaurant.delivery_fee} delivery`}</span>
          </div>

          {/* Trust badges */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400">
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              FSSAI Verified
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Freshly Prepared
            </span>
            {restaurant.delivery_time_min <= 30 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-900/20 dark:text-blue-400">
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Under 30 min
              </span>
            )}
          </div>

          {restaurant.minimum_order_amount > 0 && (
            <p className="mt-1.5 text-xs text-gray-400">
              Min. order: {currencySymbol}{restaurant.minimum_order_amount}
            </p>
          )}
        </div>
      </Card>
    </Link>
  );
}
