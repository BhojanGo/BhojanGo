"use client";
/**
 * The dispatch map: OpenStreetMap tiles via Leaflet (free, no key). Riders as
 * dots (teal free, kesar offered, kohl busy), kitchens with orders waiting for a
 * rider as squares, SOS alerts as red rings.
 */
import "leaflet/dist/leaflet.css";

import type * as Leaflet from "leaflet";
import { useEffect, useRef, useState } from "react";

import type { MapRider, Sos } from "@/lib/ops";

export interface Waiting { id: string; code: string; lat: number; lng: number; label: string }

const COLOUR: Record<string, string> = { available: "#0B5D66", offered: "#D4932A", busy: "#111418" };

export function DispatchMap({ centre, riders, waiting, sos }: { centre: [number, number]; riders: MapRider[]; waiting: Waiting[]; sos: Sos[] }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const layer = useRef<Leaflet.LayerGroup | null>(null);
  const L = useRef<typeof Leaflet | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let gone = false;
    void import("leaflet").then((mod) => {
      if (gone || !el.current || map.current) return;
      L.current = mod;
      map.current = mod.map(el.current, { zoomControl: true }).setView(centre, 12);
      mod.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map.current);
      layer.current = mod.layerGroup().addTo(map.current);
      setReady(true);
    });
    return () => {
      gone = true;
      map.current?.remove();
      map.current = null;
    };
    // the centre only matters for the first view
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = L.current, g = layer.current;
    if (!ready || !m || !g) return;
    g.clearLayers();
    for (const r of riders) {
      m.circleMarker([r.lat, r.lng], { radius: 8, color: "#fff", weight: 2, fillColor: COLOUR[r.status] ?? "#0B5D66", fillOpacity: 1 })
        .bindTooltip(`Rider ${r.rider_id.slice(0, 4)} · ${r.status}${r.order_id ? ` · order #${r.order_id.replace(/-/g, "").slice(0, 6).toUpperCase()}` : ""}`)
        .addTo(g);
    }
    for (const w of waiting) {
      m.rectangle([[w.lat - 0.0012, w.lng - 0.0016], [w.lat + 0.0012, w.lng + 0.0016]], { color: "#D4932A", weight: 2, fillOpacity: 0.6 })
        .bindTooltip(`${w.code} waiting for a rider · ${w.label}`).addTo(g);
    }
    for (const a of sos) {
      if (a.lat == null || a.lng == null) continue;
      m.circleMarker([a.lat, a.lng], { radius: 16, color: "#B3261E", weight: 4, fillOpacity: 0 }).bindTooltip(`SOS · rider ${a.rider_id.slice(0, 4)}`).addTo(g);
    }
  }, [ready, riders, waiting, sos]);

  return <div ref={el} className="h-[460px] w-full overflow-hidden rounded-2xl" role="img" aria-label="Dispatch map" />;
}
