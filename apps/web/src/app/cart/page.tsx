"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useCartStore } from "@/store/cart";

function BillRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-gray-600 dark:text-gray-300">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

export default function CartPage() {
  const t = useTranslations("cart");
  const router = useRouter();
  // SPR-03A-FIX2B hydration guard: Zustand-persisted cart is browser-only.
  // Server HTML and the first client render must match before persisted cart rows are shown.
  const [hasMounted, setHasMounted] = useState(false);

  useEffect(() => {
    setHasMounted(true);
  }, []);
  const {
    items,
    restaurantId,
    restaurantName,
    updateQuantity,
    removeItem,
    getSubtotal,
    getDeliveryFee,
    getPlatformFee,
    getTax,
    getDiscount,
    getGrandTotal,
    currency,
  } = useCartStore();

  const currencySymbol = currency === "INR" ? "₹" : "$";

  if (!hasMounted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-gray-950">
        <div className="text-center text-sm text-gray-500 dark:text-gray-400">Loading cart...</div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-gray-950">
        <div className="text-center">
          <div className="mb-4 text-6xl">🛒</div>
          <h2 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">{t("empty")}</h2>
          <p className="mb-6 text-gray-500 dark:text-gray-400">{t("emptySubtext")}</p>
          <Link
            href="/restaurants"
            className="inline-block rounded-lg bg-emerald-600 px-6 py-2.5 font-semibold text-white transition hover:bg-emerald-700"
          >
            {t("browseRestaurants")}
          </Link>
        </div>
      </div>
    );
  }

  const subtotal = getSubtotal();
  const deliveryFee = getDeliveryFee();
  const platformFee = getPlatformFee();
  const tax = getTax();
  const discount = getDiscount();
  const grandTotal = getGrandTotal();

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <div className="mx-auto max-w-2xl px-4 py-6 pb-24">
        <div className="mb-6 flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-gray-300 text-gray-700 transition hover:bg-gray-100 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
            aria-label="Go back"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">{t("title")}</h1>
        </div>

        {restaurantName && (
          <div className="mb-4 flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm dark:bg-gray-900">
            <span className="text-sm text-gray-500 dark:text-gray-400">{t("from", { restaurant: restaurantName })}</span>
            {restaurantId && (
              <Link href={`/restaurants/${restaurantId}`} className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400">
                Add more
              </Link>
            )}
          </div>
        )}

        <div className="mb-4 divide-y divide-gray-100 rounded-xl bg-white shadow-sm dark:divide-gray-800 dark:bg-gray-900">
          {items.map((item) => (
            <div key={item.menuItemId} className="flex items-center gap-4 px-4 py-4">
              {item.imageUrl && (
                <div className="relative h-14 w-16 flex-shrink-0 overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800">
                  <Image src={item.imageUrl} alt={item.name} fill className="object-cover" />
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-1.5">
                  <span
                    className={`flex h-4 w-4 items-center justify-center rounded-sm border-2 ${
                      item.isVeg ? "border-green-500" : "border-red-500"
                    }`}
                    aria-label={item.isVeg ? "Vegetarian item" : "Non-vegetarian item"}
                    title={item.isVeg ? "Vegetarian" : "Non-vegetarian"}
                  >
                    <span className={`h-2 w-2 rounded-full ${item.isVeg ? "bg-green-500" : "bg-red-500"}`} />
                  </span>
                  <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400">
                    {item.isVeg ? "Veg" : "Non-veg"}
                  </span>
                </div>
                <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{item.name}</p>
                <p className="mt-0.5 text-sm text-gray-600 dark:text-gray-300">
                  {currencySymbol}{item.price.toFixed(2)} × {item.quantity} = {currencySymbol}
                  {(item.price * item.quantity).toFixed(2)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => updateQuantity(item.menuItemId, item.quantity - 1)}
                  className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-300 text-lg leading-none text-gray-700 transition hover:border-emerald-500 hover:text-emerald-600 dark:border-gray-700 dark:text-gray-200"
                  aria-label={`Decrease quantity for ${item.name}`}
                >
                  −
                </button>
                <span className="w-6 text-center text-sm font-semibold text-gray-900 dark:text-white">{item.quantity}</span>
                <button
                  onClick={() => updateQuantity(item.menuItemId, item.quantity + 1)}
                  className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-300 text-lg leading-none text-gray-700 transition hover:border-emerald-500 hover:text-emerald-600 dark:border-gray-700 dark:text-gray-200"
                  aria-label={`Increase quantity for ${item.name}`}
                >
                  +
                </button>
                <button
                  onClick={() => removeItem(item.menuItemId)}
                  className="ml-1 text-gray-400 transition hover:text-red-500"
                  aria-label={`Remove ${item.name}`}
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="mb-6 rounded-xl bg-white px-4 py-4 shadow-sm dark:bg-gray-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Bill Summary</h3>
          <div className="space-y-2 text-sm">
            <BillRow label="Items Total" value={`${currencySymbol}${subtotal.toFixed(2)}`} />
            <BillRow label="Delivery Fee" value={deliveryFee === 0 ? "FREE" : `${currencySymbol}${deliveryFee.toFixed(2)}`} />
            <BillRow label="Platform Fee" value={`${currencySymbol}${platformFee.toFixed(2)}`} />
            <BillRow label="Tax / GST (5%)" value={`${currencySymbol}${tax.toFixed(2)}`} />
            <BillRow label="Discount" value={discount === 0 ? `${currencySymbol}0.00` : `-${currencySymbol}${discount.toFixed(2)}`} />
            <div className="h-px bg-gray-100 dark:bg-gray-800" />
            <div className="flex justify-between text-base font-bold text-gray-900 dark:text-white">
              <span>Grand Total</span>
              <span>{currencySymbol}{grandTotal.toFixed(2)}</span>
            </div>
          </div>
        </div>

        <button
          onClick={() => router.push("/checkout")}
          className="w-full rounded-xl bg-emerald-600 py-3 font-semibold text-white transition hover:bg-emerald-700"
        >
          {t("checkout")} · {currencySymbol}{grandTotal.toFixed(2)}
        </button>
      </div>
    </div>
  );
}
