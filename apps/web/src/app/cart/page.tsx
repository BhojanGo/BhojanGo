"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useCartStore } from "@/store/cart";

export default function CartPage() {
  const t = useTranslations("cart");
  const router = useRouter();
  const { items, restaurantName, restaurantSlug, updateQuantity, removeItem, getSubtotal, getTax, getTotal, deliveryFee } =
    useCartStore();

  if (items.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="text-center">
          <div className="text-6xl mb-4">🛒</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">{t("empty")}</h2>
          <p className="text-gray-500 mb-6">{t("emptySubtext")}</p>
          <Link
            href="/restaurants"
            className="inline-block px-6 py-2.5 bg-emerald-500 text-white rounded-lg font-semibold hover:bg-emerald-700 transition"
          >
            {t("browseRestaurants")}
          </Link>
        </div>
      </div>
    );
  }

  const subtotal = getSubtotal();
  const tax = getTax();
  const total = getTotal();

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.back()}
            className="w-9 h-9 rounded-full border border-gray-300 flex items-center justify-center hover:bg-gray-100 transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-xl font-bold text-gray-900">{t("title")}</h1>
        </div>

        {/* Restaurant name */}
        {restaurantName && (
          <div className="bg-white rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
            <span className="text-sm text-gray-500">{t("from", { restaurant: restaurantName })}</span>
            {restaurantSlug && (
              <Link href={`/restaurants/${restaurantSlug}`} className="text-sm text-emerald-500 hover:underline">
                Add more
              </Link>
            )}
          </div>
        )}

        {/* Items */}
        <div className="bg-white rounded-xl divide-y divide-gray-100 mb-4">
          {items.map((item) => (
            <div key={item.menuItemId} className="flex items-center gap-4 px-4 py-4">
              {item.imageUrl && (
                <div className="relative w-16 h-14 rounded-lg overflow-hidden flex-shrink-0">
                  <Image src={item.imageUrl} alt={item.name} fill className="object-cover" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 mb-0.5">
                  <span
                    className={`w-3 h-3 rounded-sm border ${
                      item.isVeg ? "border-green-500" : "border-red-500"
                    } flex items-center justify-center`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${item.isVeg ? "bg-green-500" : "bg-red-500"}`} />
                  </span>
                </div>
                <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
                <p className="text-sm text-gray-600 mt-0.5">
                  ×{item.quantity} = ${(item.price * item.quantity).toFixed(2)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => updateQuantity(item.menuItemId, item.quantity - 1)}
                  className="w-7 h-7 rounded-full border border-gray-300 flex items-center justify-center text-gray-600 hover:border-emerald-500 hover:text-emerald-500 transition text-lg leading-none"
                >
                  −
                </button>
                <span className="w-5 text-center text-sm font-semibold">{item.quantity}</span>
                <button
                  onClick={() => updateQuantity(item.menuItemId, item.quantity + 1)}
                  className="w-7 h-7 rounded-full border border-gray-300 flex items-center justify-center text-gray-600 hover:border-emerald-500 hover:text-emerald-500 transition text-lg leading-none"
                >
                  +
                </button>
                <button
                  onClick={() => removeItem(item.menuItemId)}
                  className="ml-1 text-gray-400 hover:text-red-500 transition"
                  aria-label="Remove item"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Bill summary */}
        <div className="bg-white rounded-xl px-4 py-4 mb-6 space-y-3">
          <h3 className="font-semibold text-gray-900 text-sm">Bill Summary</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>{t("subtotal")}</span>
              <span>${subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>{t("deliveryFee")}</span>
              <span>{deliveryFee === 0 ? "FREE" : `$${deliveryFee.toFixed(2)}`}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>{t("tax")}</span>
              <span>${tax.toFixed(2)}</span>
            </div>
            <div className="h-px bg-gray-100" />
            <div className="flex justify-between font-semibold text-gray-900">
              <span>{t("total")}</span>
              <span>${total.toFixed(2)}</span>
            </div>
          </div>
        </div>

        <button
          onClick={() => router.push("/checkout")}
          className="w-full py-3 bg-emerald-500 hover:bg-emerald-700 text-white font-semibold rounded-xl transition"
        >
          {t("checkout")} · ${total.toFixed(2)}
        </button>
      </div>
    </div>
  );
}
