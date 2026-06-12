"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AdminLayout from "@/components/layout/AdminLayout";
import { adminApi } from "@/lib/api";

type PricingModel = "percentage_commission" | "flat_fee_per_order" | "monthly_subscription";

interface Restaurant {
  id: string;
  name: string;
  currency: string;
  pricing_model: PricingModel;
  commission_rate: number;
  flat_fee_per_order: number;
  monthly_subscription_fee: number;
  delivery_radius_km: number;
}

interface RestaurantList {
  items: Restaurant[];
  total: number;
}

const MODELS: { value: PricingModel; label: string }[] = [
  { value: "percentage_commission", label: "Percentage commission" },
  { value: "flat_fee_per_order", label: "Flat fee per order" },
  { value: "monthly_subscription", label: "Monthly subscription" },
];

export default function PricingPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Restaurant | null>(null);
  const [model, setModel] = useState<PricingModel>("percentage_commission");
  const [commissionRate, setCommissionRate] = useState("0.20");
  const [flatFee, setFlatFee] = useState("0");
  const [subFee, setSubFee] = useState("0");
  const [message, setMessage] = useState("");

  const { data } = useQuery({
    queryKey: ["admin-restaurants-pricing"],
    queryFn: async () => {
      const { data } = await adminApi.get("/restaurant/restaurants?limit=100");
      return data as RestaurantList;
    },
  });

  function selectRestaurant(r: Restaurant) {
    setSelected(r);
    setModel(r.pricing_model);
    setCommissionRate(String(r.commission_rate ?? 0.2));
    setFlatFee(String(r.flat_fee_per_order ?? 0));
    setSubFee(String(r.monthly_subscription_fee ?? 0));
    setMessage("");
  }

  const mutation = useMutation({
    mutationFn: async () => {
      if (!selected) return;
      const body: Record<string, unknown> = { pricing_model: model };
      if (model === "percentage_commission") body.commission_rate = Number(commissionRate);
      if (model === "flat_fee_per_order") body.flat_fee_per_order = Number(flatFee);
      if (model === "monthly_subscription") body.monthly_subscription_fee = Number(subFee);
      await adminApi.put(`/restaurant/restaurants/${selected.id}/pricing`, body);
    },
    onSuccess: () => {
      setMessage("Pricing updated.");
      queryClient.invalidateQueries({ queryKey: ["admin-restaurants-pricing"] });
    },
    onError: () => setMessage("Failed to update pricing."),
  });

  return (
    <AdminLayout>
      <div className="p-6">
        <h1 className="text-xl font-bold text-white mb-1">Restaurant Pricing</h1>
        <p className="text-sm text-gray-500 mb-6">Configure each restaurant&apos;s commission / fee model.</p>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Restaurant list */}
          <div className="bg-gray-900 rounded-xl p-4 lg:col-span-2">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-left">
                  <th className="py-2 font-medium">Restaurant</th>
                  <th className="py-2 font-medium">Model</th>
                  <th className="py-2 font-medium text-right">Value</th>
                  <th className="py-2 font-medium text-right">Radius</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((r) => (
                  <tr key={r.id} className="border-t border-gray-800">
                    <td className="py-2.5 text-white">{r.name}</td>
                    <td className="py-2.5 text-gray-400">{r.pricing_model.replace(/_/g, " ")}</td>
                    <td className="py-2.5 text-right text-gray-300">
                      {r.pricing_model === "percentage_commission"
                        ? `${(r.commission_rate * 100).toFixed(1)}%`
                        : r.pricing_model === "flat_fee_per_order"
                        ? `${r.currency} ${r.flat_fee_per_order.toFixed(2)}`
                        : `${r.currency} ${r.monthly_subscription_fee.toFixed(0)}/mo`}
                    </td>
                    <td className="py-2.5 text-right text-gray-500">{r.delivery_radius_km} km</td>
                    <td className="py-2.5 text-right">
                      <button
                        onClick={() => selectRestaurant(r)}
                        className="text-emerald-500 hover:underline text-xs"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
                {!data && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-gray-600">Loading…</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Editor */}
          <div className="bg-gray-900 rounded-xl p-5">
            {selected ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  mutation.mutate();
                }}
                className="space-y-4"
              >
                <p className="font-semibold text-white">{selected.name}</p>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Pricing model</label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value as PricingModel)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
                  >
                    {MODELS.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </div>

                {model === "percentage_commission" && (
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Commission rate (0–1, e.g. 0.20 = 20%)</label>
                    <input
                      type="number" step="0.01" min="0" max="1"
                      value={commissionRate}
                      onChange={(e) => setCommissionRate(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
                    />
                  </div>
                )}
                {model === "flat_fee_per_order" && (
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Flat fee per order ({selected.currency})</label>
                    <input
                      type="number" step="0.01" min="0"
                      value={flatFee}
                      onChange={(e) => setFlatFee(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
                    />
                  </div>
                )}
                {model === "monthly_subscription" && (
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Monthly subscription fee ({selected.currency})</label>
                    <input
                      type="number" step="1" min="0"
                      value={subFee}
                      onChange={(e) => setSubFee(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
                    />
                  </div>
                )}

                {message && <p className="text-xs text-gray-400">{message}</p>}
                <button
                  type="submit"
                  disabled={mutation.isPending}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm font-semibold rounded-lg transition"
                >
                  {mutation.isPending ? "Saving…" : "Save pricing"}
                </button>
              </form>
            ) : (
              <p className="text-sm text-gray-500">Select a restaurant to edit its pricing model.</p>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
