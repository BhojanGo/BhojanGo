"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useCartStore } from "@/store/cart";

interface Address {
  id: string;
  label: string;
  street: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
}

type PaymentMethod = "stripe" | "wallet" | "cod" | "razorpay";

export default function CheckoutPage() {
  const t = useTranslations("checkout");
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();
  const cart = useCartStore();

  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("stripe");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isIndia = user?.country === "IN";

  // Redirect if not authenticated
  if (!isAuthenticated) {
    router.replace("/login?redirect=/checkout");
    return null;
  }

  // Redirect if cart empty
  if (cart.items.length === 0) {
    router.replace("/");
    return null;
  }

  const { data: addresses } = useQuery<Address[]>({
    queryKey: ["addresses"],
    queryFn: async () => {
      const { data } = await api.get("/user/me/addresses");
      return data;
    },
  });

  const { data: walletBalance } = useQuery<{ balance: number; currency: string }>({
    queryKey: ["wallet-balance"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/balance");
      return data;
    },
  });

  async function handlePlaceOrder() {
    if (!selectedAddressId) {
      setError("Please select a delivery address.");
      return;
    }
    setError("");
    setLoading(true);

    try {
      const address = addresses?.find((a) => a.id === selectedAddressId);
      if (!address) throw new Error("Address not found");

      // Create order
      const orderPayload = {
        restaurant_id: cart.restaurantId,
        items: cart.items.map((item) => ({
          menu_item_id: item.menuItemId,
          quantity: item.quantity,
          unit_price: item.price,
          customizations: item.customizations,
        })),
        delivery_address: {
          street: address.street,
          city: address.city,
          state: address.state,
          postal_code: address.postal_code,
          country: address.country,
        },
        payment_method: paymentMethod,
        subtotal: cart.getSubtotal(),
        delivery_fee: cart.deliveryFee,
        tax: cart.getTax(),
        total: cart.getTotal(),
      };

      const { data: order } = await api.post("/order/orders", orderPayload);

      // Initiate payment
      if (paymentMethod !== "cod") {
        const { data: paymentIntent } = await api.post("/payment/payments/initiate", {
          order_id: order.id,
          amount: cart.getTotal(),
          currency: isIndia ? "INR" : "USD",
          payment_method: paymentMethod,
          country: isIndia ? "IN" : "US",
        });

        if (paymentMethod === "stripe" && paymentIntent.client_secret) {
          // Redirect to Stripe checkout or handle inline
          router.push(`/checkout/payment?order_id=${order.id}&client_secret=${paymentIntent.client_secret}`);
          return;
        }

        if (paymentMethod === "razorpay" && paymentIntent.razorpay_order_id) {
          router.push(`/checkout/payment?order_id=${order.id}&razorpay_order_id=${paymentIntent.razorpay_order_id}`);
          return;
        }
      }

      // Wallet / COD — order is placed
      cart.clearCart();
      router.push(`/orders/${order.id}?success=true`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to place order. Please try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  const total = cart.getTotal();
  const currencySymbol = isIndia ? "₹" : "$";

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

        {/* Delivery Address */}
        <section className="bg-white rounded-xl p-4 mb-4">
          <h2 className="font-semibold text-gray-900 mb-3">{t("deliveryAddress")}</h2>
          {!addresses?.length ? (
            <button className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-brand-500 hover:border-brand-400 transition">
              + {t("addAddress")}
            </button>
          ) : (
            <div className="space-y-2">
              {addresses.map((addr) => (
                <label
                  key={addr.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition ${
                    selectedAddressId === addr.id
                      ? "border-brand-500 bg-brand-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="address"
                    value={addr.id}
                    checked={selectedAddressId === addr.id}
                    onChange={() => setSelectedAddressId(addr.id)}
                    className="mt-0.5 accent-brand-500"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{addr.label}</p>
                    <p className="text-xs text-gray-500">
                      {addr.street}, {addr.city}, {addr.state} {addr.postal_code}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          )}
        </section>

        {/* Order Summary */}
        <section className="bg-white rounded-xl p-4 mb-4">
          <h2 className="font-semibold text-gray-900 mb-3">{t("orderSummary")}</h2>
          <div className="space-y-2">
            {cart.items.map((item) => (
              <div key={item.menuItemId} className="flex justify-between text-sm text-gray-700">
                <span>
                  {item.name} × {item.quantity}
                </span>
                <span>
                  {currencySymbol}
                  {(item.price * item.quantity).toFixed(2)}
                </span>
              </div>
            ))}
            <div className="h-px bg-gray-100 my-2" />
            <div className="flex justify-between text-sm text-gray-500">
              <span>Subtotal</span>
              <span>{currencySymbol}{cart.getSubtotal().toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500">
              <span>Delivery</span>
              <span>{cart.deliveryFee === 0 ? "FREE" : `${currencySymbol}${cart.deliveryFee.toFixed(2)}`}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500">
              <span>Tax</span>
              <span>{currencySymbol}{cart.getTax().toFixed(2)}</span>
            </div>
            <div className="h-px bg-gray-100 my-2" />
            <div className="flex justify-between font-semibold text-gray-900">
              <span>Total</span>
              <span>{currencySymbol}{total.toFixed(2)}</span>
            </div>
          </div>
        </section>

        {/* Payment Method */}
        <section className="bg-white rounded-xl p-4 mb-6">
          <h2 className="font-semibold text-gray-900 mb-3">{t("paymentMethod")}</h2>
          <div className="space-y-2">
            {[
              {
                value: isIndia ? "razorpay" : "stripe",
                label: t("card"),
                icon: "💳",
              },
              {
                value: "wallet",
                label: `${t("wallet")} ${walletBalance ? `(${currencySymbol}${walletBalance.balance.toFixed(2)})` : ""}`,
                icon: "👛",
              },
              { value: "cod", label: t("cod"), icon: "💵" },
            ].map((option) => (
              <label
                key={option.value}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition ${
                  paymentMethod === option.value
                    ? "border-brand-500 bg-brand-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <input
                  type="radio"
                  name="payment"
                  value={option.value}
                  checked={paymentMethod === (option.value as PaymentMethod)}
                  onChange={() => setPaymentMethod(option.value as PaymentMethod)}
                  className="accent-brand-500"
                />
                <span className="text-lg">{option.icon}</span>
                <span className="text-sm font-medium text-gray-900">{option.label}</span>
              </label>
            ))}
          </div>
        </section>

        {error && (
          <div className="bg-red-50 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">{error}</div>
        )}

        <button
          onClick={handlePlaceOrder}
          disabled={loading || !selectedAddressId}
          className="w-full py-3 bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white font-semibold rounded-xl transition"
        >
          {loading ? t("processing") : `${t("placeOrder")} · ${currencySymbol}${total.toFixed(2)}`}
        </button>
      </div>
    </div>
  );
}
