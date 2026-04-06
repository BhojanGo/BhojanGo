"use client";

import { useQuery } from "@tanstack/react-query";
import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";

interface DailyRevenue {
  date: string;
  revenue: number;
  orders: number;
}

interface TopRestaurant {
  id: string;
  name: string;
  orders: number;
  revenue: number;
}

function Bar({ value, max, label, color = "bg-emerald-600" }: { value: number; max: number; label: string; color?: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-400 w-24 truncate">{label}</span>
      <div className="flex-1 bg-gray-800 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-300 w-12 text-right">{value.toLocaleString()}</span>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: revenueData } = useQuery({
    queryKey: ["admin-revenue-7d"],
    queryFn: async () => {
      const { data } = await adminApi.get("/order/admin/analytics/revenue?days=7");
      return data as DailyRevenue[];
    },
  });

  const { data: topRestaurants } = useQuery({
    queryKey: ["admin-top-restaurants"],
    queryFn: async () => {
      const { data } = await adminApi.get("/order/admin/analytics/top-restaurants?limit=10");
      return data as TopRestaurant[];
    },
  });

  const maxRevenue = Math.max(...(revenueData?.map((d) => d.revenue) ?? [1]));
  const maxOrders = Math.max(...(topRestaurants?.map((r) => r.orders) ?? [1]));

  return (
    <AdminLayout>
      <div className="p-6">
        <h1 className="text-xl font-bold text-white mb-6">Analytics</h1>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Revenue chart — simplified bar chart */}
          <div className="bg-gray-900 rounded-xl p-5">
            <h2 className="font-semibold text-white mb-4">Revenue (Last 7 Days)</h2>
            {revenueData ? (
              <div className="space-y-3">
                {revenueData.map((d) => (
                  <div key={d.date}>
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                      <span>{new Date(d.date).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</span>
                      <span>{d.orders} orders</span>
                    </div>
                    <div className="bg-gray-800 rounded-full h-6 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-emerald-600 to-emerald-500 h-6 flex items-center pl-3 transition-all"
                        style={{ width: `${(d.revenue / maxRevenue) * 100}%` }}
                      >
                        <span className="text-xs text-white font-medium">
                          ${(d.revenue / 100).toFixed(0)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {Array.from({ length: 7 }).map((_, i) => (
                  <div key={i} className="h-8 bg-gray-800 rounded animate-pulse" />
                ))}
              </div>
            )}
          </div>

          {/* Top restaurants */}
          <div className="bg-gray-900 rounded-xl p-5">
            <h2 className="font-semibold text-white mb-4">Top Restaurants by Orders</h2>
            {topRestaurants ? (
              <div className="space-y-3">
                {topRestaurants.map((r) => (
                  <Bar
                    key={r.id}
                    label={r.name}
                    value={r.orders}
                    max={maxOrders}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-6 bg-gray-800 rounded animate-pulse" />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
