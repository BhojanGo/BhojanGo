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
    <Link href={`/restaurants/${restaurant.slug}`}>
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
