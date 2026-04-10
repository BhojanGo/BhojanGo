"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";

type Restaurant = {
  id: string;
  name: string;
  cuisine_type: string[];
  status: string;
  is_active: boolean;
  city: string;
  average_rating: number;
  created_at: string;
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-900/40 text-emerald-400",
  pending_approval: "bg-amber-900/40 text-amber-400",
  suspended: "bg-red-900/40 text-red-400",
  inactive: "bg-gray-800 text-gray-400",
};

export default function RestaurantsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const perPage = 20;
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["admin-restaurants", search, statusFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams({
        limit: String(perPage),
        offset: String((page - 1) * perPage),
      });
      if (search) params.set("search", search);

      // Use admin/pending endpoint for pending filter
      if (statusFilter === "pending_approval") {
        const res = await adminApi.get(`/restaurant/restaurants/admin/pending?${params}`);
        return { restaurants: res.data, total: res.data.length };
      }

      const res = await adminApi.get(`/restaurant/restaurants?${params}`);
      return { restaurants: res.data.items || res.data.restaurants || res.data, total: res.data.total || res.data.length };
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => adminApi.post(`/restaurant/restaurants/${id}/approve`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-restaurants"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => adminApi.post(`/restaurant/restaurants/${id}/reject`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-restaurants"] }),
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      adminApi.patch(`/restaurant/restaurants/${id}`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-restaurants"] }),
  });

  const restaurants: Restaurant[] = data?.restaurants || [];

  return (
    <AdminLayout>
    <div className="p-6">
      <h1 className="text-2xl font-bold text-white mb-6">Restaurant Management</h1>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Search restaurants..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-4 py-2 text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-600"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-600 bg-gray-900 px-4 py-2 text-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-600"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : restaurants.length === 0 ? (
        <div className="text-center py-12 text-gray-400">No restaurants found</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="min-w-full divide-y divide-gray-700">
            <thead className="bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Cuisine</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">City</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Rating</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Active</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-gray-900 divide-y divide-gray-700">
              {restaurants.map((r) => (
                <tr key={r.id} className="hover:bg-gray-800">
                  <td className="px-6 py-4 font-medium text-white">{r.name}</td>
                  <td className="px-6 py-4 text-gray-400">{r.cuisine_type?.join(", ") || "\u2014"}</td>
                  <td className="px-6 py-4 text-gray-400">{r.city || "\u2014"}</td>
                  <td className="px-6 py-4 text-gray-400">{r.average_rating?.toFixed(1) || "\u2014"}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${STATUS_COLORS[r.status] || "bg-gray-800 text-gray-400"}`}>
                      {r.status?.replace("_", " ") || "unknown"}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => toggleActive.mutate({ id: r.id, is_active: !r.is_active })}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${r.is_active ? "bg-emerald-600" : "bg-gray-600"}`}
                    >
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${r.is_active ? "translate-x-6" : "translate-x-1"}`} />
                    </button>
                  </td>
                  <td className="px-6 py-4 space-x-2">
                    {r.status === "pending_approval" && (
                      <>
                        <button
                          onClick={() => approveMutation.mutate(r.id)}
                          disabled={approveMutation.isPending}
                          className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => rejectMutation.mutate(r.id)}
                          disabled={rejectMutation.isPending}
                          className="rounded bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {r.status === "suspended" && (
                      <button
                        onClick={() => approveMutation.mutate(r.id)}
                        className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        Reactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="rounded border border-gray-600 px-4 py-2 text-sm text-gray-300 disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-gray-400">Page {page}</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={restaurants.length < perPage}
          className="rounded border border-gray-600 px-4 py-2 text-sm text-gray-300 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
    </AdminLayout>
  );
}
