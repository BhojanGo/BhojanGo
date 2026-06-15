"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";

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
  const [showAddressForm, setShowAddressForm] = useState(false);
  const [addressForm, setAddressForm] = useState({
    label: "",
    street: "",
    city: "",
    state: "",
    postal_code: "",
    country: user?.country ?? "US",
  });
  const [savingAddress, setSavingAddress] = useState(false);

  const queryClient = useQueryClient();
  const isIndia = user?.country === "IN";

  const { data: addresses } = useQuery<Address[]>({
    queryKey: ["addresses"],
    queryFn: async () => {
      const { data } = await api.get("/user/me/addresses");
      return data;
    },
    enabled: !!isAuthenticated,
  });

  const { data: walletBalance } = useQuery<{ balance: number; currency: string }>({
    queryKey: ["wallet-balance"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/balance");
      return data;
    },
    enabled: !!isAuthenticated,
  });

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

  async function handleSaveAddress(e: React.FormEvent) {
    e.preventDefault();
    if (!addressForm.street.trim() || !addressForm.city.trim()) {
      setError("Street and city are required.");
      return;
    }
    setSavingAddress(true);
    setError("");
    try {
      const { data: saved } = await api.post("/user/me/addresses", addressForm);
      await queryClient.invalidateQueries({ queryKey: ["addresses"] });
      setSelectedAddressId(saved.id);
      setShowAddressForm(false);
      setAddressForm({ label: "", street: "", city: "", state: "", postal_code: "", country: user?.country ?? "US" });
    } catch {
      setError("Failed to save address. Please try again.");
    } finally {
      setSavingAddress(false);
    }
  }

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

      // Map the UI payment choice to the order-svc payment_method enum.
      const orderPaymentMethod =
        paymentMethod === "wallet" ? "wallet" : paymentMethod === "cod" ? "cash_on_delivery" : "card";
      const currency = isIndia ? "INR" : "USD";

      // Create order. The server is the source of truth for money — it recomputes
      // subtotal/tax/total from the live menu, so we only send line items + address.
      const orderPayload = {
        restaurant_id: cart.restaurantId,
        items: cart.items.map((item) => ({
          menu_item_id: item.menuItemId,
          quantity: item.quantity,
          customizations: item.customizations,
        })),
        delivery_address: {
          street: address.street,
          city: address.city,
          state: address.state,
          zip: address.postal_code,
          country: address.country,
        },
        payment_method: orderPaymentMethod,
      };

      const { data: order } = await api.post("/order/orders", orderPayload);

      // Amount must be in the smallest currency unit (cents/paise) for the payment service.
      const amountMinor = Math.round((order.total ?? cart.getTotal()) * 100);

      // Initiate payment (skip for cash on delivery)
      if (paymentMethod !== "cod") {
        const { data: paymentIntent } = await api.post("/payment/payments/initiate", {
          order_id: order.id,
          amount: amountMinor,
          currency,
          payment_method_type: paymentMethod === "wallet" ? "wallet" : "card",
          country: isIndia ? "IN" : "US",
        });

        const params = new URLSearchParams({
          order_id: order.id,
          provider: paymentIntent.provider,
          amount: String(paymentIntent.amount ?? amountMinor),
          currency,
        });
        if (paymentMethod === "stripe" && paymentIntent.client_secret) {
          params.set("client_secret", paymentIntent.client_secret);
          cart.clearCart();
          router.push(`/checkout/payment?${params.toString()}`);
          return;
        }
        if (paymentMethod === "razorpay" && paymentIntent.razorpay_order_id) {
          params.set("razorpay_order_id", paymentIntent.razorpay_order_id);
          cart.clearCart();
          router.push(`/checkout/payment?${params.toString()}`);
          return;
        }
        // Wallet — payment is settled synchronously by the initiate call.
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

  const subtotal = cart.getSubtotal();
  const deliveryFee = cart.getDeliveryFee();
  const platformFee = cart.getPlatformFee();
  const tax = cart.getTax();
  const discount = cart.getDiscount();
  const total = cart.getGrandTotal();
  const currencySymbol = cart.currency === "INR" ? "₹" : "$";

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
          {addresses && addresses.length > 0 && (
            <div className="space-y-2 mb-3">
              {addresses.map((addr) => (
                <label
                  key={addr.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition ${
                    selectedAddressId === addr.id
                      ? "border-emerald-500 bg-emerald-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="address"
                    value={addr.id}
                    checked={selectedAddressId === addr.id}
                    onChange={() => setSelectedAddressId(addr.id)}
                    className="mt-0.5 accent-emerald-500"
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

          {showAddressForm ? (
            <form onSubmit={handleSaveAddress} className="space-y-3 border border-gray-200 rounded-lg p-4">
              <p className="text-sm font-medium text-gray-900">New delivery address</p>
              <input
                type="text"
                placeholder="Label (e.g. Home, Work)"
                value={addressForm.label}
                onChange={(e) => setAddressForm({ ...addressForm, label: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
              />
              <input
                type="text"
                placeholder="Street address *"
                required
                value={addressForm.street}
                onChange={(e) => setAddressForm({ ...addressForm, street: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
              />
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="City *"
                  required
                  value={addressForm.city}
                  onChange={(e) => setAddressForm({ ...addressForm, city: e.target.value })}
                  className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
                />
                <input
                  type="text"
                  placeholder="State"
                  value={addressForm.state}
                  onChange={(e) => setAddressForm({ ...addressForm, state: e.target.value })}
                  className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
                />
              </div>
              <input
                type="text"
                placeholder="Postal code"
                value={addressForm.postal_code}
                onChange={(e) => setAddressForm({ ...addressForm, postal_code: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={savingAddress}
                  className="flex-1 py-2 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm font-semibold rounded-lg transition"
                >
                  {savingAddress ? "Saving..." : "Save Address"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddressForm(false)}
                  className="px-4 py-2 border border-gray-300 text-sm text-gray-600 rounded-lg hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setShowAddressForm(true)}
              className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-emerald-500 hover:border-emerald-400 transition"
            >
              + {t("addAddress")}
            </button>
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
              <span>Items Total</span>
              <span>{currencySymbol}{subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500">
              <span>Delivery Fee</span>
              <span>{deliveryFee === 0 ? "FREE" : `${currencySymbol}${deliveryFee.toFixed(2)}`}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500">
              <span>Platform Fee</span>
              <span>{currencySymbol}{platformFee.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500">
              <span>Tax / GST (5%)</span>
              <span>{currencySymbol}{tax.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500">
              <span>Discount</span>
              <span>{discount === 0 ? `${currencySymbol}0.00` : `-${currencySymbol}${discount.toFixed(2)}`}</span>
            </div>
            <div className="h-px bg-gray-100 my-2" />
            <div className="flex justify-between font-semibold text-gray-900">
              <span>Grand Total</span>
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
                    ? "border-emerald-500 bg-emerald-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <input
                  type="radio"
                  name="payment"
                  value={option.value}
                  checked={paymentMethod === (option.value as PaymentMethod)}
                  onChange={() => setPaymentMethod(option.value as PaymentMethod)}
                  className="accent-emerald-500"
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
          className="w-full py-3 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold rounded-xl transition"
        >
          {loading ? t("processing") : `${t("placeOrder")} · ${currencySymbol}${total.toFixed(2)}`}
        </button>
      </div>
    </div>
  );
}
