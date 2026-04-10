"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

const LOCALES = [
  { value: "en-US", label: "English (US)" },
  { value: "en-IN", label: "English (India)" },
  { value: "hi-IN", label: "हिंदी (India)" },
];

const CURRENCIES = [
  { value: "USD", label: "USD — US Dollar" },
  { value: "INR", label: "INR — Indian Rupee" },
];

export default function ProfilePage() {
  const t = useTranslations("profile");
  const router = useRouter();
  const qc = useQueryClient();
  const { isAuthenticated, user, setUser, logout } = useAuthStore();

  const [form, setForm] = useState({
    full_name: user?.full_name ?? "",
    email: user?.email ?? "",
    phone: user?.phone ?? "",
    preferred_locale: user?.preferred_locale ?? "en-US",
    preferred_currency: user?.preferred_currency ?? "USD",
  });
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: async (payload: typeof form) => {
      const { data } = await api.patch("/user/me", payload);
      return data;
    },
    onSuccess: (updatedUser) => {
      setUser(updatedUser);
      void qc.invalidateQueries({ queryKey: ["me"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  if (!isAuthenticated) {
    router.replace("/login?redirect=/profile");
    return null;
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-gray-900 mb-6">{t("title")}</h1>

        {/* Avatar */}
        <div className="flex items-center gap-4 mb-6 bg-white rounded-xl p-4">
          <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 text-2xl font-bold">
            {user?.full_name?.[0]?.toUpperCase() ?? "?"}
          </div>
          <div>
            <p className="font-semibold text-gray-900">{user?.full_name}</p>
            <p className="text-sm text-gray-500">{user?.email}</p>
            <p className="text-xs mt-0.5 text-gray-400 capitalize">{user?.role}</p>
          </div>
        </div>

        {/* Personal Info */}
        <div className="bg-white rounded-xl p-5 mb-4">
          <h2 className="font-semibold text-gray-900 mb-4">{t("personalInfo")}</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("name")}</label>
              <input
                name="full_name"
                type="text"
                value={form.full_name}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("email")}</label>
              <input
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("phone")}</label>
              <input
                name="phone"
                type="tel"
                value={form.phone}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition text-sm"
              />
            </div>
          </div>
        </div>

        {/* Preferences */}
        <div className="bg-white rounded-xl p-5 mb-4">
          <h2 className="font-semibold text-gray-900 mb-4">{t("preferences")}</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("language")}</label>
              <select
                name="preferred_locale"
                value={form.preferred_locale}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 outline-none transition text-sm bg-white"
              >
                {LOCALES.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("currency")}</label>
              <select
                name="preferred_currency"
                value={form.preferred_currency}
                onChange={handleChange}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:border-emerald-500 outline-none transition text-sm bg-white"
              >
                {CURRENCIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending}
          className="w-full py-3 bg-emerald-500 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold rounded-xl transition mb-3"
        >
          {mutation.isPending ? "..." : saved ? `✓ ${t("saved")}` : t("save")}
        </button>

        {mutation.isError && (
          <p className="text-sm text-red-600 text-center mb-3">Failed to save. Please try again.</p>
        )}

        <button
          onClick={handleLogout}
          className="w-full py-3 border border-red-300 text-red-600 font-semibold rounded-xl hover:bg-red-50 transition text-sm"
        >
          Sign Out
        </button>
      </div>
    </div>
  );
}
