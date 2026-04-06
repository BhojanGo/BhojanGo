"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";
import type { Restaurant } from "@bhojango/types";

export default function RestaurantsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-restaurants", search, page],
    queryFn: async () => {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String((page - 1) * limit),
      });
      if (search) params.set("q", search);
      const { data } = await adminApi.get(`/restaurant/restaurants?${params.toString()}`);
      return data as { items: Restaurant[]; total: number };
    },
  });

  const toggleActive = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      await adminApi.patch(`/restaurant/restaurants/${id}`, { is_active });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-restaurants"] }),
  });

  return (
    <AdminLayout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-white">Restaurants</h1>
          <div className="text-sm text-gray-500">{data?.total ?? 0} total</div>
        </div>

        <div className="mb-5">
          <input
            type="search"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search restaurants..."
            className="w-80 px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:border-emerald-600 outline-none"
          />
        </div>

        <div className="bg-gray-900 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  {["Name", "City", "Cuisine", "Rating", "Orders", "Status", "Actions"].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading &&
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={7} className="py-3 px-4">
                        <div className="h-5 bg-gray-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))}
                {data?.items.map((r) => (
                  <tr key={r.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="py-3 px-4 text-sm font-medium text-white">{r.name}</td>
                    <td className="py-3 px-4 text-sm text-gray-400">{r.address?.city ?? "—"}</td>
                    <td className="py-3 px-4 text-sm text-gray-400">
                      {r.cuisine_types?.slice(0, 2).join(", ")}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-300">
                      ⭐ {r.rating?.toFixed(1) ?? "—"}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-400">{r.total_orders ?? 0}</td>
                    <td className="py-3 px-4">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        r.is_active ? "bg-green-900/50 text-green-400" : "bg-gray-800 text-gray-500"
                      }`}>
                        {r.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => toggleActive.mutate({ id: r.id, is_active: !r.is_active })}
                        className={`text-xs px-2.5 py-1 rounded-lg border transition ${
                          r.is_active
                            ? "border-red-800 text-red-400 hover:bg-red-900/20"
                            : "border-green-800 text-green-400 hover:bg-green-900/20"
                        }`}
                      >
                        {r.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {(data?.total ?? 0) > limit && (
            <div className="flex items-center justify-between px-5 py-4 border-t border-gray-800">
              <p className="text-sm text-gray-500">
                Page {page} of {Math.ceil((data?.total ?? 0) / limit)}
              </p>
              <div className="flex gap-2">
                <button onClick={() => setPage(page - 1)} disabled={page === 1} className="px-3 py-1.5 text-sm bg-gray-800 text-gray-400 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition">
                  Previous
                </button>
                <button onClick={() => setPage(page + 1)} disabled={page * limit >= (data?.total ?? 0)} className="px-3 py-1.5 text-sm bg-gray-800 text-gray-400 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition">
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
