"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import type { Order } from "@bhojango/types";

const STATUS_STEPS = [
  "confirmed",
  "preparing",
  "ready_for_pickup",
  "picked_up",
  "delivered",
] as const;

type TrackingMessage = {
  type: "location_update" | "status_update" | "ping";
  lat?: number;
  lng?: number;
  status?: string;
  driver_name?: string;
  eta_minutes?: number;
};

function StatusTimeline({ status }: { status: string }) {
  const t = useTranslations("orders");
  const currentIndex = STATUS_STEPS.indexOf(status as (typeof STATUS_STEPS)[number]);

  return (
    <div className="relative">
      <div className="flex justify-between">
        {STATUS_STEPS.map((step, i) => {
          const isPast = i <= currentIndex;
          const isCurrent = i === currentIndex;
          return (
            <div key={step} className="flex flex-col items-center flex-1">
              <div
                className={`w-5 h-5 rounded-full border-2 z-10 transition-colors ${
                  isCurrent
                    ? "bg-emerald-500 border-emerald-500"
                    : isPast
                    ? "bg-emerald-400 border-emerald-400"
                    : "bg-white border-gray-300"
                }`}
              />
              <p className={`text-xs mt-1 text-center ${isPast ? "text-emerald-700" : "text-gray-400"}`}>
                {t(`status.${step}` as never) as string}
              </p>
            </div>
          );
        })}
      </div>
      {/* Connector line */}
      <div className="absolute top-2.5 left-0 right-0 h-0.5 bg-gray-200 -z-0">
        <div
          className="h-full bg-emerald-400 transition-all"
          style={{
            width: `${Math.max(0, (currentIndex / (STATUS_STEPS.length - 1)) * 100)}%`,
          }}
        />
      </div>
    </div>
  );
}

export default function OrderDetailPage() {
  const t = useTranslations("orders");
  const tTracking = useTranslations("tracking");
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { isAuthenticated, accessToken } = useAuthStore();

  const wsRef = useRef<WebSocket | null>(null);
  const [tracking, setTracking] = useState<{
    lat?: number;
    lng?: number;
    driverName?: string;
    etaMinutes?: number;
    wsStatus: "connecting" | "connected" | "disconnected";
  }>({ wsStatus: "disconnected" });

  const { data: order, refetch } = useQuery({
    queryKey: ["order", params.id],
    queryFn: async () => {
      const { data } = await api.get(`/order/orders/${params.id}`);
      return data as Order;
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || ["delivered", "cancelled"].includes(status)) return false;
      return 30_000;
    },
  });

  // WebSocket tracking for active orders
  useEffect(() => {
    if (!order || ["delivered", "cancelled"].includes(order.status)) return;
    if (!accessToken) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8004"}/ws/track/${params.id}?token=${accessToken}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    setTracking((prev) => ({ ...prev, wsStatus: "connecting" }));

    ws.onopen = () => setTracking((prev) => ({ ...prev, wsStatus: "connected" }));
    ws.onclose = () => setTracking((prev) => ({ ...prev, wsStatus: "disconnected" }));

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as TrackingMessage;
        if (msg.type === "location_update") {
          setTracking((prev) => ({
            ...prev,
            lat: msg.lat,
            lng: msg.lng,
            driverName: msg.driver_name ?? prev.driverName,
            etaMinutes: msg.eta_minutes ?? prev.etaMinutes,
          }));
        } else if (msg.type === "status_update") {
          void refetch();
        }
      } catch {
        // ignore malformed messages
      }
    };

    return () => {
      ws.close();
    };
  }, [order?.status, accessToken, params.id, refetch]);

  if (!isAuthenticated) {
    router.replace(`/login?redirect=/orders/${params.id}`);
    return null;
  }

  if (!order) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-gray-500 text-sm">Loading order...</p>
        </div>
      </div>
    );
  }

  const isActive = !["delivered", "cancelled"].includes(order.status);
  const currencySymbol = order.currency === "INR" ? "₹" : "$";

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push("/orders")}
            className="w-9 h-9 rounded-full border border-gray-300 flex items-center justify-center hover:bg-gray-100 transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              {t("orderNumber", { id: order.id.slice(0, 8).toUpperCase() })}
            </h1>
            <p className="text-xs text-gray-500">
              {new Date(order.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
        </div>

        {/* Live tracking banner */}
        {isActive && tracking.wsStatus === "connected" && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm font-medium text-emerald-800">{tTracking("liveTracking")}</span>
            </div>
            {tracking.etaMinutes && (
              <span className="text-sm text-emerald-700">
                {tTracking("eta", { time: tracking.etaMinutes })}
              </span>
            )}
          </div>
        )}

        {/* Driver info */}
        {tracking.driverName && (
          <div className="bg-white rounded-xl px-4 py-3 mb-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 font-semibold">
              {tracking.driverName[0]}
            </div>
            <div>
              <p className="text-xs text-gray-500">{tTracking("driverAssigned")}</p>
              <p className="text-sm font-medium text-gray-900">
                {tTracking("driverName", { name: tracking.driverName })}
              </p>
            </div>
          </div>
        )}

        {/* Status timeline */}
        {order.status !== "cancelled" && (
          <div className="bg-white rounded-xl p-5 mb-4">
            <StatusTimeline status={order.status} />
          </div>
        )}

        {order.status === "cancelled" && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-4">
            <p className="text-sm font-semibold text-red-700">Order Cancelled</p>
            {order.cancellation_reason && (
              <p className="text-xs text-red-600 mt-1">{order.cancellation_reason}</p>
            )}
          </div>
        )}

        {/* Map placeholder (real map integration would use react-leaflet or @vis.gl/react-google-maps) */}
        {isActive && tracking.lat && tracking.lng && (
          <div className="bg-gray-200 rounded-xl h-48 mb-4 flex items-center justify-center">
            <p className="text-sm text-gray-500">
              Driver at {tracking.lat.toFixed(4)}, {tracking.lng.toFixed(4)}
            </p>
          </div>
        )}

        {/* Restaurant & Items */}
        <div className="bg-white rounded-xl p-4 mb-4">
          <p className="font-semibold text-gray-900 mb-3">{order.restaurant_name}</p>
          <div className="space-y-2">
            {order.items?.map((item) => (
              <div key={item.id} className="flex justify-between text-sm text-gray-700">
                <span>
                  {item.name} × {item.quantity}
                </span>
                <span>
                  {currencySymbol}
                  {(item.unit_price * item.quantity).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
          <div className="h-px bg-gray-100 my-3" />
          <div className="flex justify-between font-semibold text-gray-900">
            <span>Total</span>
            <span>
              {currencySymbol}
              {order.total?.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Delivery address */}
        {order.delivery_address && (
          <div className="bg-white rounded-xl p-4 mb-4">
            <p className="text-sm font-semibold text-gray-900 mb-1">{t("deliveryAddress")}</p>
            <p className="text-sm text-gray-500">
              {order.delivery_address.street}, {order.delivery_address.city},{" "}
              {order.delivery_address.state} {order.delivery_address.postal_code}
            </p>
          </div>
        )}

        {/* Reorder button for completed */}
        {order.status === "delivered" && (
          <button
            onClick={() => {
              // Navigate back to restaurant — cart handling happens there
              if (order.restaurant_slug) router.push(`/restaurants/${order.restaurant_slug}`);
            }}
            className="w-full py-3 border border-emerald-500 text-emerald-500 font-semibold rounded-xl hover:bg-emerald-50 transition"
          >
            {t("reorder")}
          </button>
        )}
      </div>
    </div>
  );
}
