"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";

interface PaymentTransaction {
  id: string;
  order_id: string;
  user_id: string;
  amount: number;
  currency: string;
  status: string;
  provider: string;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  succeeded: "bg-green-900/50 text-green-400",
  pending: "bg-yellow-900/50 text-yellow-400",
  failed: "bg-red-900/50 text-red-400",
  refunded: "bg-blue-900/50 text-blue-400",
};

export default function PaymentsPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const limit = 20;
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["admin-payments", statusFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), limit: String(limit) });
      if (statusFilter !== "all") params.set("status", statusFilter);
      const res = await adminApi.get(`/api/payment/payments?${params}`);
      return res.data;
    },
  });

  const refundMutation = useMutation({
    mutationFn: async (orderId: string) => {
      await adminApi.post(`/api/payment/payments/${orderId}/refund`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-payments"] }),
  });

  const payments: PaymentTransaction[] = data?.data ?? [];

  const formatCurrency = (amount: number, currency: string) =>
    new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
      style: "currency",
      currency,
    }).format(amount);

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white">Payments</h1>
          <div className="flex gap-2">
            {["all", "succeeded", "pending", "failed", "refunded"].map((s) => (
              <button
                key={s}
                onClick={() => { setStatusFilter(s); setPage(1); }}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium capitalize transition ${
                  statusFilter === s ? "bg-orange-500 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-800 bg-gray-900">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-800 bg-gray-950 text-gray-400">
              <tr>
                <th className="px-4 py-3">Transaction ID</th>
                <th className="px-4 py-3">Order</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">Loading...</td></tr>
              ) : payments.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No payments found</td></tr>
              ) : (
                payments.map((payment) => (
                  <tr key={payment.id} className="text-gray-300 hover:bg-gray-800/50">
                    <td className="px-4 py-3 font-mono text-xs">{payment.id.slice(0, 8)}...</td>
                    <td className="px-4 py-3 font-mono text-xs">{payment.order_id.slice(0, 8)}...</td>
                    <td className="px-4 py-3 font-medium text-white">
                      {formatCurrency(payment.amount, payment.currency)}
                    </td>
                    <td className="px-4 py-3 capitalize">{payment.provider}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_COLORS[payment.status] ?? "bg-gray-700 text-gray-400"
                      }`}>
                        {payment.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(payment.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      {payment.status === "succeeded" && (
                        <button
                          onClick={() => refundMutation.mutate(payment.order_id)}
                          disabled={refundMutation.isPending}
                          className="rounded bg-red-900/50 px-2 py-1 text-xs text-red-400 hover:bg-red-900 disabled:opacity-50"
                        >
                          Refund
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-sm text-gray-400">
          <span>Page {page}</span>
          <div className="flex gap-2">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50">Previous</button>
            <button onClick={() => setPage((p) => p + 1)} disabled={payments.length < limit} className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50">Next</button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
