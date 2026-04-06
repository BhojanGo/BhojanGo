"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";

interface Driver {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  is_active: boolean;
  current_order_id: string | null;
  city: string;
  rating: number;
  total_deliveries: number;
}

export default function DriversPage() {
  const [filter, setFilter] = useState<"all" | "active" | "idle">("all");
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-drivers", filter, page],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), limit: String(limit) });
      if (filter !== "all") params.set("status", filter);
      const res = await adminApi.get(`/api/user/users?role=driver&${params}`);
      return res.data;
    },
  });

  const drivers: Driver[] = data?.data ?? [];

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white">Drivers</h1>
          <div className="flex gap-2">
            {(["all", "active", "idle"] as const).map((f) => (
              <button
                key={f}
                onClick={() => { setFilter(f); setPage(1); }}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium capitalize transition ${
                  filter === f ? "bg-emerald-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-800 bg-gray-900">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-800 bg-gray-950 text-gray-400">
              <tr>
                <th className="px-4 py-3">Driver</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">City</th>
                <th className="px-4 py-3">Rating</th>
                <th className="px-4 py-3">Deliveries</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">Loading...</td></tr>
              ) : drivers.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">No drivers found</td></tr>
              ) : (
                drivers.map((driver) => (
                  <tr key={driver.id} className="text-gray-300 hover:bg-gray-800/50">
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-white">{driver.full_name}</p>
                        <p className="text-xs text-gray-500">{driver.email}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">{driver.phone}</td>
                    <td className="px-4 py-3">{driver.city}</td>
                    <td className="px-4 py-3">{driver.rating?.toFixed(1) ?? "N/A"}</td>
                    <td className="px-4 py-3">{driver.total_deliveries}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        driver.current_order_id
                          ? "bg-green-900/50 text-green-400"
                          : "bg-gray-700 text-gray-400"
                      }`}>
                        {driver.current_order_id ? "On delivery" : "Idle"}
                      </span>
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
            <button onClick={() => setPage((p) => p + 1)} disabled={drivers.length < limit} className="rounded bg-gray-800 px-3 py-1 disabled:opacity-50">Next</button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
