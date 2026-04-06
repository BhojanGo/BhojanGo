"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";
import type { User } from "@bhojango/types";

const ROLES = ["all", "customer", "driver", "restaurant_owner", "admin", "super_admin"];

export default function UsersPage() {
  const [roleFilter, setRoleFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const limit = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", roleFilter, search, page],
    queryFn: async () => {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String((page - 1) * limit),
      });
      if (roleFilter !== "all") params.set("role", roleFilter);
      if (search) params.set("q", search);
      const { data } = await adminApi.get(`/user/admin/users?${params.toString()}`);
      return data as { items: User[]; total: number };
    },
  });

  return (
    <AdminLayout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-white">Users</h1>
          <p className="text-sm text-gray-500">{data?.total ?? 0} total</p>
        </div>

        <div className="flex gap-3 mb-5 flex-wrap">
          <input
            type="search"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search users..."
            className="w-64 px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:border-orange-500 outline-none"
          />
          {ROLES.map((r) => (
            <button
              key={r}
              onClick={() => { setRoleFilter(r); setPage(1); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition ${
                roleFilter === r ? "bg-orange-500 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {r.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="bg-gray-900 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  {["Name", "Email", "Phone", "Role", "Country", "Joined", "Status"].map((h) => (
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
                {data?.items.map((user) => (
                  <tr key={user.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="py-3 px-4 text-sm font-medium text-white">{user.full_name}</td>
                    <td className="py-3 px-4 text-sm text-gray-400">{user.email}</td>
                    <td className="py-3 px-4 text-sm text-gray-400">{user.phone ?? "—"}</td>
                    <td className="py-3 px-4">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 capitalize">
                        {user.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-400">{user.country ?? "—"}</td>
                    <td className="py-3 px-4 text-xs text-gray-500">
                      {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        user.is_active !== false ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
                      }`}>
                        {user.is_active !== false ? "Active" : "Suspended"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(data?.total ?? 0) > limit && (
            <div className="flex items-center justify-between px-5 py-4 border-t border-gray-800">
              <p className="text-sm text-gray-500">Page {page} of {Math.ceil((data?.total ?? 0) / limit)}</p>
              <div className="flex gap-2">
                <button onClick={() => setPage(page - 1)} disabled={page === 1} className="px-3 py-1.5 text-sm bg-gray-800 text-gray-400 rounded-lg disabled:opacity-40 hover:bg-gray-700">Previous</button>
                <button onClick={() => setPage(page + 1)} disabled={page * limit >= (data?.total ?? 0)} className="px-3 py-1.5 text-sm bg-gray-800 text-gray-400 rounded-lg disabled:opacity-40 hover:bg-gray-700">Next</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
