"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";
import type { Order } from "@bhojango/types";

const STATUSES = ["all", "pending", "confirmed", "preparing", "ready_for_pickup", "picked_up", "delivered", "cancelled"];

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-900/50 text-yellow-400",
  confirmed: "bg-blue-900/50 text-blue-400",
  preparing: "bg-amber-900/50 text-emerald-500",
  ready_for_pickup: "bg-purple-900/50 text-purple-400",
  picked_up: "bg-indigo-900/50 text-indigo-400",
  delivered: "bg-green-900/50 text-green-400",
  cancelled: "bg-red-900/50 text-red-400",
};

export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-orders", statusFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String((page - 1) * limit),
      });
      if (statusFilter !== "all") params.set("status", statusFilter);
      const { data } = await adminApi.get(`/order/orders?${params.toString()}`);
      return data as { items: Order[]; total: number };
    },
  });

  const totalPages = Math.ceil((data?.total ?? 0) / limit);

  return (
    <AdminLayout>
      <div className="p-6">
        <h1 className="text-xl font-bold text-white mb-6">Orders</h1>

        {/* Status filter tabs */}
        <div className="flex gap-2 mb-5 flex-wrap">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition ${
                statusFilter === s
                  ? "bg-emerald-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {s.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="bg-gray-900 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  {["Order ID", "Customer", "Restaurant", "Amount", "Status", "Time", ""].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading &&
                  Array.from({ length: 10 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={7} className="py-3 px-4">
                        <div className="h-5 bg-gray-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))}
                {data?.items.map((order) => (
                  <tr key={order.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="py-3 px-4 text-sm text-gray-300">
                      #{order.id.slice(0, 8).toUpperCase()}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-300">{order.user_id?.slice(0, 8)}</td>
                    <td className="py-3 px-4 text-sm text-gray-300">{order.restaurant_name ?? "—"}</td>
                    <td className="py-3 px-4 text-sm text-gray-300">
                      {order.currency === "INR" ? "₹" : "$"}{order.total?.toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[order.status] ?? "bg-gray-800 text-gray-400"}`}>
                        {order.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-gray-500">
                      {new Date(order.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <Link href={`/orders/${order.id}`} className="text-xs text-emerald-500 hover:underline">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-4 border-t border-gray-800">
              <p className="text-sm text-gray-500">
                Showing {(page - 1) * limit + 1}–{Math.min(page * limit, data?.total ?? 0)} of {data?.total} orders
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm bg-gray-800 text-gray-400 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 text-sm bg-gray-800 text-gray-400 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
