"use client";

/**
 * Zone map: OpenStreetMap tiles via Leaflet (free, no API key).
 * - view: zones as coloured polygons; click one to select it
 * - draw: click the map to add corners; the parent finishes the shape
 * - edit: drag the selected zone's corners
 * Coordinates are [lng, lat] like GeoJSON; Leaflet wants [lat, lng].
 */
import "leaflet/dist/leaflet.css";

import type * as Leaflet from "leaflet";
import { useEffect, useRef, useState, useLayoutEffect } from "react";

import type { Zone } from "@/lib/markets";

type LngLat = [number, number];
export type MapMode = "view" | "draw" | "edit";

const toLatLng = ([lng, lat]: LngLat): [number, number] => [lat, lng];

export function ZoneMap({
  center,
  zones,
  selectedId,
  mode,
  draft,
  onSelect,
  onDraftChange,
}: {
  center: [number, number];
  zones: Zone[];
  selectedId: string | null;
  mode: MapMode;
  /** Corners being drawn, or the selected zone's corners being edited (no closing point). */
  draft: LngLat[];
  onSelect: (id: string) => void;
  onDraftChange: (points: LngLat[]) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const L = useRef<typeof Leaflet | null>(null);
  const zoneLayer = useRef<Leaflet.LayerGroup | null>(null);
  const draftLayer = useRef<Leaflet.LayerGroup | null>(null);
  const fitted = useRef(false);
  const [, setReady] = useState(false); // re-render once Leaflet has loaded
  // Latest props for Leaflet event handlers registered once.
  const latest = useRef({ mode, draft, onDraftChange, onSelect });
  useLayoutEffect(() => {
    latest.current = { mode, draft, onDraftChange, onSelect };
  });

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const leaflet = (await import("leaflet")).default;
      if (cancelled || !el.current || map.current) return;
      L.current = leaflet;
      const m = leaflet.map(el.current, { zoomControl: false }).setView(center, 12);
      leaflet.control.zoom({ position: "bottomright" }).addTo(m); // top edge holds the drawing bar
      leaflet
        .tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        })
        .addTo(m);
      zoneLayer.current = leaflet.layerGroup().addTo(m);
      draftLayer.current = leaflet.layerGroup().addTo(m);
      m.on("click", (e: Leaflet.LeafletMouseEvent) => {
        const { mode: md, draft: d, onDraftChange: change } = latest.current;
        if (md === "draw") change([...d, [e.latlng.lng, e.latlng.lat]]);
      });
      map.current = m;
      setReady(true);
      setTimeout(() => m.invalidateSize(), 0);
    })();
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Zones.
  useEffect(() => {
    const leaflet = L.current;
    const layer = zoneLayer.current;
    if (!leaflet || !layer || !map.current) return;
    layer.clearLayers();
    const bounds: [number, number][] = [];
    for (const z of zones) {
      if (mode === "edit" && z.id === selectedId) continue; // drawn by the edit layer
      const ring = z.polygon.coordinates[0].map(toLatLng);
      bounds.push(...ring);
      const selected = z.id === selectedId;
      const poly = leaflet.polygon(ring, {
        color: z.color,
        weight: selected ? 3 : 2,
        fillOpacity: selected ? 0.25 : 0.15,
        dashArray: z.status === "draft" ? "3 6" : z.status === "paused" ? "6 5" : undefined,
      });
      poly.bindTooltip(`${z.name} · ${z.status}`, { sticky: true });
      poly.on("click", () => latest.current.mode === "view" && latest.current.onSelect(z.id));
      poly.addTo(layer);
    }
    if (!fitted.current && bounds.length) {
      map.current.fitBounds(bounds, { padding: [24, 24] });
      fitted.current = true;
    }
  });

  // The shape being drawn or edited.
  useEffect(() => {
    const leaflet = L.current;
    const layer = draftLayer.current;
    if (!leaflet || !layer) return;
    layer.clearLayers();
    if (mode === "view" || draft.length === 0) return;
    const pts = draft.map(toLatLng);
    const shape =
      pts.length >= 3
        ? leaflet.polygon(pts, { color: "#0B5D66", weight: 3, fillOpacity: 0.2 })
        : leaflet.polyline(pts, { color: "#0B5D66", weight: 3 });
    shape.addTo(layer);
    const live = [...pts];
    draft.forEach((p, i) => {
      const marker = leaflet.marker(toLatLng(p), {
        draggable: true,
        keyboard: true,
        title: `Corner ${i + 1}`,
        icon: leaflet.divIcon({
          className: "",
          html: '<span style="display:block;width:14px;height:14px;border-radius:999px;background:#fff;border:3px solid #0B5D66;box-sizing:border-box"></span>',
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        }),
      });
      // Move the outline while dragging; tell the parent once the corner is dropped
      // (re-rendering mid-drag would remove the marker being dragged).
      marker.on("drag", (e) => {
        const ll = (e.target as Leaflet.Marker).getLatLng();
        live[i] = [ll.lat, ll.lng];
        shape.setLatLngs(live);
      });
      marker.on("dragend", () => {
        latest.current.onDraftChange(live.map(([lat, lng]) => [lng, lat] as LngLat));
      });
      marker.addTo(layer);
    });
  });

  // Leaflet adds its own classes to the map element, so React must never
  // re-render that element's className: the mode-dependent bits go on a wrapper.
  return (
    <div
      role="application"
      aria-label={mode === "draw" ? "Map: click to add the zone's corners" : "Map of zones"}
      className={`absolute inset-0 ${mode === "draw" ? "[&_.leaflet-container]:cursor-crosshair" : ""}`}
    >
      <div ref={el} className="h-full w-full" />
    </div>
  );
}
