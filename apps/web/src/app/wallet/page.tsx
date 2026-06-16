"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

type WalletBalance = {
  user_id: string;
  balance: number;
  currency: "USD" | "INR" | string;
  updated_at: string;
};

type WalletTransaction = {
  id: string;
  user_id: string;
  type: "credit" | "debit" | string;
  amount: number;
  currency: string;
  balance_after: number;
  description: string;
  reference_id: string | null;
  reference_type: string | null;
  created_at: string;
};

type WalletTransactionList = {
  items: WalletTransaction[];
  total: number;
  page: number;
  limit: number;
};

function formatMoney(value: number, currency: string) {
  const symbol = currency === "INR" ? "₹" : "$";
  return `${symbol}${Number(value || 0).toFixed(2)}`;
}

function useAuthHydrated() {
  const [ready, setReady] = useState(() => {
    if (typeof window === "undefined") return false;
    return useAuthStore.persist.hasHydrated();
  });

  useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setReady(true);
      return;
    }
    return useAuthStore.persist.onFinishHydration(() => setReady(true));
  }, []);

  return ready;
}

function getWalletErrorMessage(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown; message?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const message = typeof record.message === "string" ? record.message : "";
    const code = typeof record.code === "string" ? record.code : "";
    if (message && code) return `${message} (${code})`;
    if (message) return message;
    if (code) return code;
  }
  const message = (err as { response?: { data?: { message?: unknown } } })?.response?.data?.message;
  return typeof message === "string" ? message : fallback;
}

export default function WalletPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated, user } = useAuthStore();
  const authReady = useAuthHydrated();
  const [topupAmount, setTopupAmount] = useState("100");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (authReady && !isAuthenticated) {
      router.replace("/login?redirect=/wallet");
    }
  }, [authReady, isAuthenticated, router]);

  const walletBalance = useQuery<WalletBalance>({
    queryKey: ["wallet-balance"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/balance");
      return data;
    },
    enabled: authReady && isAuthenticated,
  });

  const walletTransactions = useQuery<WalletTransactionList>({
    queryKey: ["wallet-transactions"],
    queryFn: async () => {
      const { data } = await api.get("/payment/wallet/transactions?limit=20");
      return data;
    },
    enabled: authReady && isAuthenticated,
  });

  const preferredCurrency = (user as { preferred_currency?: string } | null)?.preferred_currency;
  const currency = walletBalance.data?.currency ?? preferredCurrency ?? (user?.country === "IN" ? "INR" : "USD");
  const balance = Number(walletBalance.data?.balance ?? 0);
  const balanceLabel = useMemo(() => formatMoney(balance, currency), [balance, currency]);

  async function handleTopup(e: React.FormEvent) {
    e.preventDefault();
    const amount = Number(topupAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Enter a valid top-up amount.");
      return;
    }

    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const { data } = await api.post<WalletBalance>("/payment/wallet/topup", {
        amount,
        currency,
        payment_method_id: "demo_wallet_topup",
      });
      queryClient.setQueryData(["wallet-balance"], data);
      await queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] });
      setMessage(`Wallet topped up by ${formatMoney(amount, currency)}.`);
    } catch (err: unknown) {
      setError(getWalletErrorMessage(err, "Failed to top up wallet. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  if (!authReady) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <p className="text-sm text-gray-500">Loading wallet...</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div data-testid="wallet-ready" className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="mb-6">
          <p className="text-sm font-medium text-emerald-600">BhojanGo Wallet</p>
          <h1 className="text-2xl font-bold text-gray-900">Wallet</h1>
          <p className="mt-1 text-sm text-gray-500">Demo balance, top-up, and transaction ledger for SPR-03B validation.</p>
        </div>

        <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <p className="text-sm text-gray-500">Current Balance</p>
          <p data-testid="wallet-balance" data-balance={balance.toFixed(2)} className="mt-2 text-4xl font-bold text-gray-900">
            {walletBalance.isLoading ? "Loading..." : balanceLabel}
          </p>
          <p className="mt-2 text-xs text-gray-500">Default non-production demo seed is applied once and recorded in the ledger.</p>
        </section>

        <section className="mt-5 rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-900">Add Money</h2>
          <p className="mt-1 text-sm text-gray-500">Dummy top-up until real payment gateway capture is implemented.</p>
          <form onSubmit={handleTopup} className="mt-4 flex flex-col gap-3 sm:flex-row">
            <label className="sr-only" htmlFor="wallet-topup-amount">Top-up amount</label>
            <input
              id="wallet-topup-amount"
              aria-label="Top-up amount"
              type="number"
              min="1"
              step="0.01"
              value={topupAmount}
              onChange={(e) => setTopupAmount(e.target.value)}
              className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
            />
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-emerald-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Adding..." : "Add Money"}
            </button>
          </form>
          {message && <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
          {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
        </section>

        <section className="mt-5 rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-gray-900">Transaction History</h2>
            <button
              type="button"
              onClick={() => void walletTransactions.refetch()}
              className="text-sm font-medium text-emerald-600 hover:text-emerald-700"
            >
              Refresh
            </button>
          </div>
          <div data-testid="wallet-transactions" className="mt-4 divide-y divide-gray-100">
            {walletTransactions.isLoading && <p className="py-4 text-sm text-gray-500">Loading transactions...</p>}
            {!walletTransactions.isLoading && (walletTransactions.data?.items.length ?? 0) === 0 && (
              <p className="py-4 text-sm text-gray-500">No transactions yet.</p>
            )}
            {walletTransactions.data?.items.map((txn) => (
              <div key={txn.id} className="flex items-start justify-between gap-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{txn.description}</p>
                  <p className="mt-1 text-xs text-gray-500">
                    {txn.reference_type ?? "wallet"} · {new Date(txn.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-semibold ${txn.type === "credit" ? "text-emerald-600" : "text-red-600"}`}>
                    {txn.type === "credit" ? "+" : "-"}{formatMoney(Number(txn.amount), txn.currency)}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">Balance {formatMoney(Number(txn.balance_after), txn.currency)}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
