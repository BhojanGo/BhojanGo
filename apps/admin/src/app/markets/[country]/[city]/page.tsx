"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { StatusPill } from "@/components/console/StatusPill";
import type { MapMode } from "@/components/markets/ZoneMap";
import {
  apiError,
  can,
  CHECKLIST_LABELS,
  type CityDetail,
  type MarketStatus,
  marketsApi,
  moneySymbol,
  useAdminMe,
  useCity,
  type Zone,
} from "@/lib/markets";

const ZoneMap = dynamic(() => import("@/components/markets/ZoneMap").then((m) => m.ZoneMap), { ssr: false });

type LngLat = [number, number];
const STATUSES: MarketStatus[] = ["draft", "beta", "live", "paused"];
const PALETTE = ["#0B5D66", "#5BA3AA", "#D4932A", "#2E7D86", "#7FB7BD", "#B5762A"];

function zoneLine(z: Zone, currency: string): string {
  const min = z.min_order ? `min ${moneySymbol(currency)}${Number(z.min_order).toFixed(0)}` : "no minimum";
  if (z.status === "paused") {
    const until = z.paused_until ? ` · until ${new Date(z.paused_until).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : "";
    return `Paused · ${z.pause_reason ?? "no reason given"}${until}`;
  }
  if (z.status === "draft") return "Draft · not visible to customers";
  return `${z.status === "beta" ? "Beta" : "Live"} · ${min} · ${z.area_km2} km²`;
}

function ErrorNote({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div role="alert" className="flex items-start justify-between gap-4 rounded-xl bg-danger-tint px-4 py-3 text-sm text-danger-ink">
      <span>{message}</span>
      <button type="button" onClick={onClose} className="font-bold" aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}

export default function CityPage() {
  const { country, city: code } = useParams<{ country: string; city: string }>();
  const { data: city, isLoading, error } = useCity(code);
  const { data: me } = useAdminMe();
  const qc = useQueryClient();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<MapMode>("view");
  const [draft, setDraft] = useState<LngLat[]>([]);
  const [naming, setNaming] = useState(false);
  const [newZone, setNewZone] = useState({ name: "", min_order: "" });
  const [pausing, setPausing] = useState(false);
  const [pause, setPause] = useState({ reason: "", until: "" });
  const [editingHours, setEditingHours] = useState(false);
  const [hours, setHours] = useState({ open: "", close: "" });
  const [problem, setProblem] = useState<string | null>(null);

  const canEdit = can(me, "markets.edit", code);
  const canPause = can(me, "zones.pause", code);
  const selected = city?.zones.find((z) => z.id === selectedId) ?? null;

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["markets"] });
  };
  const run = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => {
      setProblem(null);
      refresh();
    },
    onError: (e) => setProblem(apiError(e)),
  });
  const act = (fn: () => Promise<unknown>, after?: () => void) => run.mutate(fn, { onSuccess: () => after?.() });

  function startDraw() {
    setSelectedId(null);
    setDraft([]);
    setMode("draw");
    setNaming(false);
  }
  function startEdit(z: Zone) {
    setDraft(z.polygon.coordinates[0].slice(0, -1) as LngLat[]);
    setMode("edit");
  }
  function cancelMap() {
    setMode("view");
    setDraft([]);
    setNaming(false);
  }
  const closed = (pts: LngLat[]) => ({ type: "Polygon" as const, coordinates: [[...pts, pts[0]]] });

  if (isLoading || !city) {
    return (
      <ConsoleShell section="Markets" country={country} city={code}>
        {error ? <p role="alert" className="rounded-xl bg-danger-tint p-4 text-danger-ink">{apiError(error)}</p> : <p className="text-muted">Loading…</p>}
      </ConsoleShell>
    );
  }

  const sym = moneySymbol(city.country.currency);
  const overrides = city.effective_settings.filter((s) => s.source_level === "city" && s.key !== "service_hours" && s.key !== "timezone");
  const missing = Object.entries(city.launch_checklist).filter(([, ok]) => !ok);
  const tz = city.effective_settings.find((s) => s.key === "timezone");

  return (
    <ConsoleShell section="Markets" country={country} region={null} city={code}>
      <div>
        <div className="text-[13px] text-muted">
          <Link href="/markets" className="text-muted">Markets</Link> ▸ <Link href={`/markets/${country}`} className="text-muted">{city.country.name}</Link> ▸{" "}
          <Link href={`/markets/${country}?state=${city.region.code}`} className="text-muted">{city.region.name}</Link>
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
          <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.8px]">{city.name}</h1>
          <div role="radiogroup" aria-label="City status" className="flex rounded-full border border-line bg-white p-1">
            {STATUSES.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={city.status === s}
                disabled={!canEdit || run.isPending}
                onClick={() => city.status !== s && act(() => marketsApi.updateCity(code, { status: s }))}
                className={`h-10 rounded-full px-4 capitalize ${city.status === s ? "bg-peacock font-extrabold text-white" : "font-semibold text-muted"} disabled:cursor-not-allowed`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {problem && <ErrorNote message={problem} onClose={() => setProblem(null)} />}

      {missing.length > 0 && (
        <div className="rounded-xl bg-kesar-tint px-4 py-3 text-sm text-kesar-ink">
          <b>Before {city.name} can open:</b> {missing.map(([k]) => CHECKLIST_LABELS[k] ?? k).join(" · ")}
        </div>
      )}

      <div className="grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
        <div className="rounded-2xl border border-line bg-white p-6">
          <div className="text-[13px] font-semibold text-muted">Service hours</div>
          {editingHours ? (
            <form
              className="mt-2 flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                act(() => marketsApi.updateCity(code, { service_hours: hours }), () => setEditingHours(false));
              }}
            >
              <label className="text-xs text-muted">Opens<input type="time" required value={hours.open} onChange={(e) => setHours({ ...hours, open: e.target.value })} className="mt-1 block rounded-lg border border-line px-2 py-1 text-sm text-kohl" /></label>
              <label className="text-xs text-muted">Closes<input type="time" required value={hours.close} onChange={(e) => setHours({ ...hours, close: e.target.value })} className="mt-1 block rounded-lg border border-line px-2 py-1 text-sm text-kohl" /></label>
              <button type="submit" className="h-9 rounded-full bg-peacock px-4 text-sm font-bold text-white">Save</button>
              <button type="button" onClick={() => setEditingHours(false)} className="h-9 px-2 text-sm font-semibold text-muted">Cancel</button>
            </form>
          ) : (
            <>
              <div className="mt-2 text-lg font-extrabold">{city.service_hours ? `${city.service_hours.open} – ${city.service_hours.close}` : "Not set"}</div>
              <div className="mt-1 text-[13px] text-muted">
                {tz?.value as string} ·{" "}
                {canEdit ? (
                  <button type="button" className="font-bold text-peacock" onClick={() => { setHours(city.service_hours ?? { open: "07:00", close: "23:00" }); setEditingHours(true); }}>
                    Edit
                  </button>
                ) : (
                  "read only"
                )}
              </div>
            </>
          )}
        </div>
        <div className="rounded-2xl border border-line bg-white p-6">
          <div className="text-[13px] font-semibold text-muted">Money and tax</div>
          <div className="mt-2 text-lg font-extrabold">
            {city.country.currency} · {city.country.tax_regime === "gst" ? "GST" : "Stripe Tax"} · {city.country.payment_providers.map((p) => p[0].toUpperCase() + p.slice(1)).join(", ")}
          </div>
          <div className="mt-1 text-[13px] font-bold text-muted">Inherited from {city.country.name}</div>
        </div>
        <div className="rounded-2xl border border-line bg-white p-6">
          <div className="text-[13px] font-semibold text-muted">City settings</div>
          <div className="mt-2 text-lg font-extrabold">{overrides.length ? `${overrides.length} overridden here` : `All inherited from ${city.region.name}`}</div>
          <div className="mt-1 text-[13px] text-muted">
            <Link href="/pricing" className="font-bold text-peacock">Open Pricing &amp; Rules</Link>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-6">
        <section aria-label="Zones" className="flex flex-[4_1_300px] flex-col gap-1 rounded-2xl border border-line bg-white p-6">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="m-0 text-[17px] font-extrabold">Zones · {city.zones.length}</h2>
            {canEdit && (
              <button type="button" onClick={startDraw} disabled={mode !== "view"} className="h-10 rounded-full bg-peacock px-4 text-sm font-extrabold text-white disabled:opacity-50">
                + Draw zone
              </button>
            )}
          </div>
          {city.zones.length === 0 && <p className="text-sm text-muted">No zones yet. {canEdit ? "Draw the first one on the map." : ""}</p>}
          {city.zones.map((z) => (
            <button
              key={z.id}
              type="button"
              aria-pressed={z.id === selectedId}
              onClick={() => mode === "view" && setSelectedId(z.id === selectedId ? null : z.id)}
              className={`flex items-center gap-3 rounded-xl border-[1.5px] p-3 text-left text-kohl ${z.id === selectedId ? "border-peacock bg-peacock-wash" : "border-transparent"}`}
            >
              <span
                className="h-3.5 w-3.5 shrink-0 rounded"
                style={z.status === "draft" ? { border: "2px dashed #4C5A5E" } : { background: z.color }}
              />
              <span className="flex-grow">
                <b className="block">{z.name}</b>
                <span className={`text-[13px] ${z.status === "paused" ? "text-kesar-ink" : "text-muted"}`}>{zoneLine(z, city.country.currency)}</span>
              </span>
            </button>
          ))}
        </section>

        <section aria-label="Zone map" className="relative min-h-[460px] min-w-0 flex-[8_1_520px] overflow-hidden rounded-2xl border border-line bg-white">
          <ZoneMap
            center={[city.center_lat, city.center_lng]}
            zones={city.zones}
            selectedId={selectedId}
            mode={mode}
            draft={draft}
            onSelect={setSelectedId}
            onDraftChange={setDraft}
          />

          {mode === "view" && selected && canEdit && (
            <div className="absolute right-4 top-4 z-[500] flex gap-2">
              <button type="button" onClick={() => startEdit(selected)} className="h-10 rounded-full bg-white px-4 text-sm font-bold text-kohl shadow-[0_4px_14px_rgba(17,20,24,0.1)]">
                Edit shape
              </button>
            </div>
          )}

          {mode !== "view" && (
            <div className="absolute left-4 right-4 top-4 z-[500] flex flex-wrap items-center gap-2 rounded-2xl bg-white p-3 text-sm shadow-[0_8px_24px_rgba(17,20,24,0.12)]">
              <span className="flex-grow font-semibold">
                {mode === "draw"
                  ? `Click the map to add corners · ${draft.length} added`
                  : `Drag the corners of ${selected?.name ?? "the zone"}`}
              </span>
              {mode === "draw" && (
                <>
                  <button type="button" disabled={!draft.length} onClick={() => setDraft(draft.slice(0, -1))} className="h-9 rounded-full px-3 font-semibold text-muted disabled:opacity-40">
                    Undo
                  </button>
                  <button type="button" disabled={draft.length < 3} onClick={() => setNaming(true)} className="h-9 rounded-full bg-peacock px-4 font-bold text-white disabled:opacity-40">
                    Finish shape
                  </button>
                </>
              )}
              {mode === "edit" && selected && (
                <button
                  type="button"
                  onClick={() => act(() => marketsApi.updateZone(selected.id, { polygon: closed(draft) }), cancelMap)}
                  className="h-9 rounded-full bg-peacock px-4 font-bold text-white"
                >
                  Save shape
                </button>
              )}
              <button type="button" onClick={cancelMap} className="h-9 rounded-full px-3 font-semibold text-muted">
                Cancel
              </button>
            </div>
          )}

          {naming && (
            <form
              className="absolute bottom-4 left-4 z-[500] flex w-[300px] max-w-[calc(100%-32px)] flex-col gap-3 rounded-2xl bg-white p-5 shadow-[0_8px_24px_rgba(17,20,24,0.12)]"
              onSubmit={(e) => {
                e.preventDefault();
                const color = PALETTE[city.zones.length % PALETTE.length];
                act(
                  () => marketsApi.createZone(code, { name: newZone.name, polygon: closed(draft), min_order: newZone.min_order || null, color }),
                  () => {
                    cancelMap();
                    setNewZone({ name: "", min_order: "" });
                  }
                );
              }}
            >
              <b className="text-[17px]">New zone</b>
              <label className="text-[13px] text-muted">
                Name
                <input required minLength={2} value={newZone.name} onChange={(e) => setNewZone({ ...newZone, name: e.target.value })} className="mt-1 block w-full rounded-lg border border-line px-3 py-2 text-sm text-kohl" />
              </label>
              <label className="text-[13px] text-muted">
                Minimum order ({sym.trim()})
                <input type="number" min="0" step="1" value={newZone.min_order} onChange={(e) => setNewZone({ ...newZone, min_order: e.target.value })} className="mt-1 block w-full rounded-lg border border-line px-3 py-2 text-sm text-kohl" />
              </label>
              <p className="m-0 text-xs text-muted">New zones start as drafts: customers don&apos;t see them until you make them live.</p>
              <button type="submit" disabled={run.isPending} className="h-11 rounded-full bg-peacock font-bold text-white">
                Create zone
              </button>
            </form>
          )}

          {mode === "view" && selected && !naming && (
            <ZonePanel
              zone={selected}
              city={city}
              canEdit={canEdit}
              canPause={canPause}
              pausing={pausing}
              pause={pause}
              setPause={setPause}
              setPausing={setPausing}
              busy={run.isPending}
              act={act}
            />
          )}
        </section>
      </div>
    </ConsoleShell>
  );
}

function ZonePanel({
  zone,
  city,
  canEdit,
  canPause,
  pausing,
  pause,
  setPause,
  setPausing,
  busy,
  act,
}: {
  zone: Zone;
  city: CityDetail;
  canEdit: boolean;
  canPause: boolean;
  pausing: boolean;
  pause: { reason: string; until: string };
  setPause: (p: { reason: string; until: string }) => void;
  setPausing: (b: boolean) => void;
  busy: boolean;
  act: (fn: () => Promise<unknown>, after?: () => void) => void;
}) {
  const sym = moneySymbol(city.country.currency);
  const [minOrder, setMinOrder] = useState(zone.min_order ?? "");
  return (
    <div className="absolute bottom-4 left-4 z-[500] box-border flex w-[300px] max-w-[calc(100%-32px)] flex-col gap-3 rounded-2xl bg-white p-5 shadow-[0_8px_24px_rgba(17,20,24,0.12)]">
      <div className="flex items-center justify-between">
        <b className="text-[17px]">{zone.name}</b>
        <StatusPill status={zone.status} />
      </div>
      <dl className="m-0 grid grid-cols-2 gap-2 text-[13px]">
        <dt className="text-muted">Min order</dt>
        <dd className="m-0 text-right font-bold">{zone.min_order ? `${sym}${Number(zone.min_order).toFixed(0)}` : "None"}</dd>
        <dt className="text-muted">Area</dt>
        <dd className="m-0 text-right font-bold">{zone.area_km2} km²</dd>
        {zone.status === "paused" && (
          <>
            <dt className="text-muted">Paused for</dt>
            <dd className="m-0 text-right font-bold">{zone.pause_reason}</dd>
          </>
        )}
      </dl>

      {canEdit && (
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            act(() => marketsApi.updateZone(zone.id, { min_order: minOrder === "" ? null : String(minOrder) }));
          }}
        >
          <label className="flex-grow text-xs text-muted">
            Min order ({sym.trim()})
            <input type="number" min="0" value={minOrder} onChange={(e) => setMinOrder(e.target.value)} className="mt-1 block w-full rounded-lg border border-line px-2 py-1 text-sm text-kohl" />
          </label>
          <button type="submit" disabled={busy} className="h-8 rounded-full border border-line px-3 text-sm font-bold">Save</button>
        </form>
      )}

      {canEdit && zone.status === "draft" && (
        <button type="button" disabled={busy} onClick={() => act(() => marketsApi.updateZone(zone.id, { status: "live" }))} className="h-11 rounded-full bg-peacock font-bold text-white">
          Make live
        </button>
      )}
      {canEdit && (zone.status === "live" || zone.status === "beta") && !pausing && (
        <button type="button" disabled={busy} onClick={() => act(() => marketsApi.updateZone(zone.id, { status: "draft" }))} className="h-9 text-sm font-semibold text-muted">
          Back to draft
        </button>
      )}
      {canPause && zone.status === "paused" && (
        <button type="button" disabled={busy} onClick={() => act(() => marketsApi.resumeZone(zone.id))} className="h-11 rounded-full bg-peacock font-bold text-white">
          Resume deliveries
        </button>
      )}
      {canPause && (zone.status === "live" || zone.status === "beta") && !pausing && (
        <button type="button" onClick={() => setPausing(true)} className="h-11 rounded-full border-[1.5px] border-[#C9D3D4] bg-white font-bold text-kohl">
          Pause this zone…
        </button>
      )}
      {pausing && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const until = pause.until ? new Date(pause.until).toISOString() : null;
            act(() => marketsApi.pauseZone(zone.id, pause.reason, until), () => {
              setPausing(false);
              setPause({ reason: "", until: "" });
            });
          }}
        >
          <label className="text-xs text-muted">
            Why (customers see this)
            <input required minLength={3} value={pause.reason} onChange={(e) => setPause({ ...pause, reason: e.target.value })} placeholder="Heavy rain" className="mt-1 block w-full rounded-lg border border-line px-2 py-1 text-sm text-kohl" />
          </label>
          <label className="text-xs text-muted">
            Until (optional)
            <input type="datetime-local" value={pause.until} onChange={(e) => setPause({ ...pause, until: e.target.value })} className="mt-1 block w-full rounded-lg border border-line px-2 py-1 text-sm text-kohl" />
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="h-10 flex-grow rounded-full bg-kohl font-bold text-white">Pause</button>
            <button type="button" onClick={() => setPausing(false)} className="h-10 px-3 text-sm font-semibold text-muted">Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}
