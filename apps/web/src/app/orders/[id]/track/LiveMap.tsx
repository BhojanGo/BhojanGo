"use client";
// The live map on the tracking page: MapLibre GL with OpenFreeMap's free
// vector tiles (no key, no account; © OpenStreetMap contributors shown on the
// map). Markers for the kitchen (pickup), home (drop-off) and the rider; a
// solid line where the rider has actually been (the trail from the tracking
// socket: the "connected" snapshot, then each location_update) and a dashed
// line from the rider to where they're heading next (the kitchen before
// pickup, home after). No predicted kitchen-to-home route: only real movement.
// The rider marker moves on every location_update. Loaded in the browser only
// (next/dynamic, ssr: false).
import "maplibre-gl/dist/maplibre-gl.css";

import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, LngLatLike } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

export type Pt = [number, number]; // [lat, lng], as the tracking socket sends them

const STYLE = "https://tiles.openfreemap.org/styles/liberty";
// The tiles add "OpenFreeMap © OpenMapTiles Data from OpenStreetMap"; OSM's own wording goes first.
const ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';

// The worker script is served by the bundler next to the page (MapLibre can't find it on its own once bundled).
let workerSet = false;
function setWorker() {
  if (workerSet) return;
  workerSet = true;
  maplibregl.setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).href);
}

const ll = (p: Pt): [number, number] => [p[1], p[0]];

function line(points: Pt[]): GeoJSON.Feature<GeoJSON.LineString> {
  return { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: points.map(ll) } };
}

function pin(kind: "kitchen" | "home" | "rider", title: string): HTMLElement {
  const el = document.createElement("div");
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", title);
  el.title = title;
  const svg =
    kind === "kitchen"
      ? '<svg width="36" height="36" viewBox="-18 -18 36 36" aria-hidden="true"><circle r="16" fill="#FFFFFF" stroke="#111418" stroke-width="3"/><path d="M-5 -8v16M-8 -8v5a3 3 0 0 0 6 0v-5M5 -8c-3 2-3 7 0 9v7" stroke="#111418" stroke-width="2.4" fill="none" stroke-linecap="round"/></svg>'
      : kind === "home"
        ? '<svg width="38" height="38" viewBox="-19 -19 38 38" aria-hidden="true"><circle r="17" fill="#0B5D66" stroke="#FFFFFF" stroke-width="3"/><path d="M-8 1 0-7 8 1v8h-16z" fill="#FFFFFF"/></svg>'
        : '<svg width="52" height="52" viewBox="-26 -26 52 52" aria-hidden="true"><circle r="24" fill="#F6E7CC" fill-opacity="0.9"/><circle r="14" fill="#E8A93C" stroke="#FFFFFF" stroke-width="3"/></svg>';
  el.innerHTML = svg;
  return el;
}

export default function LiveMap({
  pickup,
  dropoff,
  rider,
  trail,
  heading,
  labels,
}: {
  pickup: Pt | null;
  dropoff: Pt | null;
  rider: Pt | null;
  trail: Pt[];
  /** Where the rider goes next: the kitchen before pickup, home after; null when it's over (the trail only). */
  heading: "kitchen" | "home" | null;
  labels: { map: string; kitchen: string; home: string; rider: string; failed: string };
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markers = useRef<{ kitchen?: maplibregl.Marker; home?: maplibregl.Marker; rider?: maplibregl.Marker }>({});
  const fitted = useRef<string>("");
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  // The map itself, once.
  useEffect(() => {
    if (!box.current) return;
    let m: maplibregl.Map;
    try {
      setWorker();
      m = new maplibregl.Map({
        container: box.current,
        style: STYLE,
        center: [0, 20],
        zoom: 1,
        attributionControl: { compact: false, customAttribution: ATTRIBUTION },
        cooperativeGestures: false,
        dragRotate: false,
        pitchWithRotate: false,
      });
    } catch {
      // No WebGL (or the map could not start): the page still works without it.
      queueMicrotask(() => setFailed(true));
      return;
    }
    m.touchZoomRotate.disableRotation();
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.on("load", () => {
      m.addSource("done", { type: "geojson", data: line([]) });
      m.addSource("ahead", { type: "geojson", data: line([]) });
      m.addLayer({ id: "done", type: "line", source: "done", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#0B5D66", "line-width": 5 } });
      m.addLayer({ id: "ahead", type: "line", source: "ahead", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#0B5D66", "line-width": 4, "line-opacity": 0.75, "line-dasharray": [1, 2] } });
      setReady(true);
    });
    map.current = m;
    const mk = markers.current;
    return () => {
      mk.kitchen?.remove();
      mk.home?.remove();
      mk.rider?.remove();
      markers.current = {};
      m.remove();
      map.current = null;
    };
  }, []);

  // Markers and the route, whenever the live picture changes.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const place = (key: "kitchen" | "home" | "rider", at: Pt | null, title: string) => {
      const cur = markers.current[key];
      if (!at) {
        cur?.remove();
        delete markers.current[key];
        return;
      }
      if (cur) cur.setLngLat(ll(at));
      else markers.current[key] = new maplibregl.Marker({ element: pin(key, title) }).setLngLat(ll(at)).addTo(m);
    };
    place("kitchen", pickup, labels.kitchen);
    place("home", dropoff, labels.home);
    place("rider", rider, labels.rider);

    // Where the rider has been, up to where they are now.
    const last = trail[trail.length - 1];
    const done = rider && (!last || last[0] !== rider[0] || last[1] !== rider[1]) ? [...trail, rider] : trail;
    (m.getSource("done") as GeoJSONSource | undefined)?.setData(line(done.length > 1 ? done : []));
    // From the rider to the next stop only.
    const to = heading === "kitchen" ? pickup : heading === "home" ? dropoff : null;
    (m.getSource("ahead") as GeoJSONSource | undefined)?.setData(line(rider && to ? [rider, to] : []));

    // Fit everything in view when the places change (not on every rider step, so panning isn't undone).
    const pts = [pickup, dropoff, rider, ...trail].filter(Boolean) as Pt[];
    if (!pts.length) return;
    const key = JSON.stringify([pickup, dropoff, !!rider]);
    const bounds = pts.reduce((b, p) => b.extend(ll(p) as LngLatLike), new maplibregl.LngLatBounds(ll(pts[0]!), ll(pts[0]!)));
    const pad = Math.min(64, Math.round(Math.min(m.getContainer().clientWidth, m.getContainer().clientHeight) / 6));
    if (key !== fitted.current) {
      fitted.current = key;
      m.fitBounds(bounds, { padding: pad, maxZoom: 16, duration: 0 });
    } else if (rider && !m.getBounds().contains(ll(rider) as LngLatLike)) {
      m.fitBounds(bounds, { padding: pad, maxZoom: 16 });
    }
  }, [ready, pickup, dropoff, rider, trail, heading, labels.kitchen, labels.home, labels.rider]);

  return (
    <div className="relative h-full w-full bg-[#E9EEEE]">
      {/* data-*: what the lines show, for the e2e (the lines themselves are drawn on a canvas) */}
      <div ref={box} className="h-full w-full" role="region" aria-label={labels.map} data-heading={heading ?? ""} data-trail={trail.length} />
      {failed && <p className="absolute inset-x-0 top-1/2 m-0 -translate-y-1/2 px-6 text-center text-sm text-[#4C5A5E]">{labels.failed}</p>}
    </div>
  );
}
