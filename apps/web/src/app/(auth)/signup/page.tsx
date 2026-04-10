"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function SignupPage() {
  const t = useTranslations("auth");
  const tErrors = useTranslations("errors");
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    confirmPassword: "",
    phone: "",
    country: "US",
    role: "customer",
    // Restaurant owner fields
    restaurant_name: "",
    cuisine_type: "",
    restaurant_city: "",
    // Driver fields
    vehicle_type: "bike",
    license_number: "",
    driver_city: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const isIndia = tz.startsWith("Asia/") && (tz.includes("Kolkata") || tz.includes("Calcutta") || tz.includes("Chennai") || tz.includes("Mumbai"));
    setForm(f => ({ ...f, country: isIndia ? "IN" : "US" }));
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (form.password !== form.confirmPassword) {
      setError(t("passwordsNoMatch"));
      return;
    }
    if (form.password.length < 8) {
      setError(t("weakPassword"));
      return;
    }

    // Validate role-specific required fields
    if (form.role === "restaurant_owner") {
      if (!form.restaurant_name.trim()) {
        setError("Restaurant name is required");
        return;
      }
      if (!form.restaurant_city.trim()) {
        setError("City is required for restaurant owners");
        return;
      }
    }
    if (form.role === "driver") {
      if (!form.driver_city.trim()) {
        setError("City is required for delivery partners");
        return;
      }
    }

    setLoading(true);
    try {
      const payload: Record<string, string> = {
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        country: form.country,
        preferred_currency: form.country === "IN" ? "INR" : "USD",
        preferred_locale: form.country === "IN" ? "en-IN" : "en-US",
      };
      if (form.phone) payload.phone = form.phone;

      const { data } = await api.post("/user/auth/register", payload);
      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);
      router.push("/");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        tErrors("generic");
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="text-3xl font-bold text-emerald-500">
            BhojanGo
          </Link>
          <h1 className="mt-4 text-2xl font-semibold text-gray-900">{t("signupTitle")}</h1>
          <p className="mt-1 text-gray-500">{t("signupSubtitle")}</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Role selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Sign up as</label>
              <div className="flex gap-3">
                {[
                  { value: "customer", label: "Customer" },
                  { value: "restaurant_owner", label: "Restaurant Owner" },
                  { value: "driver", label: "Delivery Partner" },
                ].map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg border cursor-pointer transition text-sm font-medium ${
                      form.role === opt.value
                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={opt.value}
                      checked={form.role === opt.value}
                      onChange={handleChange}
                      className="sr-only"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label htmlFor="full_name" className="block text-sm font-medium text-gray-700 mb-1">
                {t("name")}
              </label>
              <input
                id="full_name"
                name="full_name"
                type="text"
                autoComplete="name"
                required
                value={form.full_name}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                placeholder="Jane Doe"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                {t("email")}
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={form.email}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">
                {t("phone")}
              </label>
              <input
                id="phone"
                name="phone"
                type="tel"
                autoComplete="tel"
                value={form.phone}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                placeholder="+1 555 000 0000"
              />
            </div>

            {/* Restaurant Owner fields */}
            {form.role === "restaurant_owner" && (
              <div className="space-y-4 rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
                <p className="text-sm font-medium text-emerald-700">Restaurant Details</p>
                <div>
                  <label htmlFor="restaurant_name" className="block text-sm font-medium text-gray-700 mb-1">
                    Restaurant Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="restaurant_name"
                    name="restaurant_name"
                    type="text"
                    required
                    value={form.restaurant_name}
                    onChange={handleChange}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                    placeholder="e.g. Spice Garden"
                  />
                </div>
                <div>
                  <label htmlFor="cuisine_type" className="block text-sm font-medium text-gray-700 mb-1">
                    Cuisine Type
                  </label>
                  <input
                    id="cuisine_type"
                    name="cuisine_type"
                    type="text"
                    value={form.cuisine_type}
                    onChange={handleChange}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                    placeholder="e.g. Indian, Chinese"
                  />
                </div>
                <div>
                  <label htmlFor="restaurant_city" className="block text-sm font-medium text-gray-700 mb-1">
                    City <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="restaurant_city"
                    name="restaurant_city"
                    type="text"
                    required
                    value={form.restaurant_city}
                    onChange={handleChange}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                    placeholder="e.g. Austin"
                  />
                </div>
                <p className="text-xs text-gray-500">You&apos;ll complete your profile setup after signing up.</p>
              </div>
            )}

            {/* Driver fields */}
            {form.role === "driver" && (
              <div className="space-y-4 rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
                <p className="text-sm font-medium text-emerald-700">Delivery Partner Details</p>
                <div>
                  <label htmlFor="vehicle_type" className="block text-sm font-medium text-gray-700 mb-1">
                    Vehicle Type
                  </label>
                  <select
                    id="vehicle_type"
                    name="vehicle_type"
                    value={form.vehicle_type}
                    onChange={handleChange}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                  >
                    <option value="bike">Bike</option>
                    <option value="scooter">Scooter</option>
                    <option value="car">Car</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="license_number" className="block text-sm font-medium text-gray-700 mb-1">
                    License Number
                  </label>
                  <input
                    id="license_number"
                    name="license_number"
                    type="text"
                    value={form.license_number}
                    onChange={handleChange}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                    placeholder="e.g. DL-1234567"
                  />
                </div>
                <div>
                  <label htmlFor="driver_city" className="block text-sm font-medium text-gray-700 mb-1">
                    City <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="driver_city"
                    name="driver_city"
                    type="text"
                    required
                    value={form.driver_city}
                    onChange={handleChange}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                    placeholder="e.g. Austin"
                  />
                </div>
                <p className="text-xs text-gray-500">You&apos;ll complete your profile setup after signing up.</p>
              </div>
            )}

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                {t("password")}
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                value={form.password}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                placeholder="Min. 8 characters"
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                {t("confirmPassword")}
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                value={form.confirmPassword}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold rounded-lg transition text-sm"
            >
              {loading ? "..." : t("signUp")}
            </button>
          </form>

          <div className="mt-6 relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-white px-3 text-gray-400">{t("orContinueWith")}</span>
            </div>
          </div>

          <button
            type="button"
            className="mt-4 w-full flex items-center justify-center gap-3 py-2.5 px-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition text-sm font-medium text-gray-700"
            onClick={() => {
              window.location.href = "/api/user/auth/google";
            }}
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
            {t("google")}
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-gray-500">
          {t("hasAccount")}{" "}
          <Link href="/login" className="text-emerald-500 font-semibold hover:underline">
            {t("signIn")}
          </Link>
        </p>
      </div>
    </div>
  );
}
