"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

interface WalletBalance {
  balance: number;
  currency: string;
}

interface WalletTx {
  id: string;
  amount: number;
  type: "credit" | "debit";
  description: string;
  created_at: string;
}

export default function WalletPage() {
  const t = useTranslations("wallet");
  const router = useRouter();
  const qc = useQueryClient();
  const { isAuthenticated, user } = useAuthStore();

  const [topUpAmount, setTopUpAmount] = useState("");
  const [showTopUp, setShowTopUp] = useState(false);

  if (!isAuthenticated) {
    router.replace("/login?redirect=/wallet");
    return null;
  }

  const currencySymbol = user?.preferred_currency === "INR" ? "₹" : "$";

  const { data: balance, isLoading: balanceLoading } = useQuery<WalletBalance>({
    queryKey: ["wallet-balance"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/balance");
      return data;
    },
  });

  const { data: transactions, isLoading: txLoading } = useQuery<WalletTx[]>({
    queryKey: ["wallet-transactions"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/transactions?limit=20");
      return data;
    },
  });

  const topUpMutation = useMutation({
    mutationFn: async (amount: number) => {
      const { data } = await api.post("/payment/wallet/topup", {
        amount,
        currency: balance?.currency ?? "USD",
        payment_method: "stripe",
      });
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["wallet-balance"] });
      void qc.invalidateQueries({ queryKey: ["wallet-transactions"] });
      setTopUpAmount("");
      setShowTopUp(false);
    },
  });

  const QUICK_AMOUNTS = balance?.currency === "INR"
    ? [100, 200, 500, 1000]
    : [5, 10, 20, 50];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-gray-900 mb-6">{t("title")}</h1>

        {/* Balance card */}
        <div className="bg-gradient-to-br from-brand-500 to-brand-600 rounded-2xl p-6 mb-6 text-white">
          <p className="text-sm text-brand-100 mb-1">{t("balance")}</p>
          {balanceLoading ? (
            <div className="h-10 w-32 bg-white/20 rounded animate-pulse" />
          ) : (
            <p className="text-4xl font-bold">
              {currencySymbol}
              {balance?.balance?.toFixed(2) ?? "0.00"}
            </p>
          )}
          <button
            onClick={() => setShowTopUp(!showTopUp)}
            className="mt-4 px-5 py-2 bg-white text-brand-600 rounded-lg font-semibold text-sm hover:bg-brand-50 transition"
          >
            + {t("topUp")}
          </button>
        </div>

        {/* Top-up form */}
        {showTopUp && (
          <div className="bg-white rounded-xl p-5 mb-4">
            <h3 className="font-semibold text-gray-900 mb-4">{t("addMoney")}</h3>
            <div className="flex gap-2 mb-4 flex-wrap">
              {QUICK_AMOUNTS.map((amt) => (
                <button
                  key={amt}
                  onClick={() => setTopUpAmount(String(amt))}
                  className={`px-4 py-1.5 rounded-lg border text-sm font-medium transition ${
                    topUpAmount === String(amt)
                      ? "border-brand-500 bg-brand-50 text-brand-600"
                      : "border-gray-300 text-gray-700 hover:border-gray-400"
                  }`}
                >
                  {currencySymbol}
                  {amt}
                </button>
              ))}
            </div>
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                  {currencySymbol}
                </span>
                <input
                  type="number"
                  min="1"
                  value={topUpAmount}
                  onChange={(e) => setTopUpAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full pl-8 pr-4 py-2.5 rounded-lg border border-gray-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition text-sm"
                />
              </div>
              <button
                onClick={() => {
                  const amt = parseFloat(topUpAmount);
                  if (amt > 0) topUpMutation.mutate(amt);
                }}
                disabled={topUpMutation.isPending || !topUpAmount || parseFloat(topUpAmount) <= 0}
                className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white font-semibold rounded-lg transition text-sm"
              >
                {topUpMutation.isPending ? "..." : t("addMoney")}
              </button>
            </div>
            {topUpMutation.isError && (
              <p className="text-xs text-red-600 mt-2">Failed to add money. Please try again.</p>
            )}
          </div>
        )}

        {/* Transactions */}
        <div className="bg-white rounded-xl p-5">
          <h3 className="font-semibold text-gray-900 mb-4">{t("transactions")}</h3>

          {txLoading && (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-14 bg-gray-100 rounded-lg animate-pulse" />
              ))}
            </div>
          )}

          {!txLoading && !transactions?.length && (
            <p className="text-sm text-gray-500 text-center py-6">{t("noTransactions")}</p>
          )}

          {transactions && transactions.length > 0 && (
            <div className="space-y-3">
              {transactions.map((tx) => (
                <div key={tx.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-9 h-9 rounded-full flex items-center justify-center text-lg ${
                        tx.type === "credit"
                          ? "bg-green-50 text-green-600"
                          : "bg-red-50 text-red-500"
                      }`}
                    >
                      {tx.type === "credit" ? "↓" : "↑"}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{tx.description}</p>
                      <p className="text-xs text-gray-400">
                        {new Date(tx.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>
                  <p
                    className={`text-sm font-semibold ${
                      tx.type === "credit" ? "text-green-600" : "text-red-500"
                    }`}
                  >
                    {tx.type === "credit" ? "+" : "-"}
                    {currencySymbol}
                    {tx.amount.toFixed(2)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
