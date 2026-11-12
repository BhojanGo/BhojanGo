"use client";
// Apply with your kitchen on the web (B1): sign in with the kitchen's phone,
// tell us about the kitchen, then the partner application (FSSAI, GST and
// bank, menu). Admins approve it; the BhojanGo Partner tablet app runs it.
import { errorMessage, unwrap } from "@bhojango/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, useHydrated, useSession } from "@/lib/client";
import { Button } from "@bhojango/ui";

type City = { code: string; name: string; region: string; lat: number; lng: number };
type Application = { restaurant_id: string; name: string; done: number; total: number; current: string | null; status: string;
  commission_percent: string | null; fssai_number: string | null; gstin: string | null; steps: { key: string; title: string; done: boolean; detail: string }[] };

const input = "mt-1 block h-12 w-full rounded-card border-[1.5px] border-line-strong px-3 font-normal";

async function loadApplication(): Promise<Application | null> {
  const mine = unwrap(await api.core.GET("/api/v1/restaurants/mine"));
  if (!mine[0]) return null;
  return unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/application", { params: { path: { restaurant_id: mine[0].id } } })) as Application;
}

export default function Partner() {
  const ready = useHydrated();
  const user = useSession((s) => s.user);
  const [app, setApp] = useState<Application | null>(null);
  const reload = async () => {
    const a = await loadApplication();
    if (a) setApp(a);
  };
  useEffect(() => {
    if (!(ready && user?.role === "restaurant_owner")) return;
    let live = true;
    loadApplication().then((a) => live && a && setApp(a)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [ready, user?.role]);

  if (!ready) return <div className="mx-auto max-w-content px-5 py-14 text-muted">Loading…</div>;
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-5 py-12">
      <div>
        <p className="text-sm font-bold uppercase tracking-[1.2px] text-peacock">For kitchens</p>
        <h1 className="font-display text-5xl font-semibold tracking-[-1.2px]">Cook for your neighbourhood</h1>
        <p className="mt-3 text-lg text-muted">Commission on food only, paid weekly. You set your prices and your own offers. Customers see the whole bill, so they trust your prices.</p>
      </div>
      {!user ? (
        <div className="rounded-card bg-white p-6">
          <p className="mb-4">Sign in with your kitchen&apos;s phone number to apply.</p>
          <Link href="/sign-in?next=/partner" className="inline-flex h-12 items-center rounded-pill bg-peacock px-6 font-extrabold text-white">Sign in to apply</Link>
        </div>
      ) : user.role === "restaurant_owner" ? (
        app ? <Steps app={app} onSaved={reload} /> : <p className="text-muted">Loading your application…</p>
      ) : user.role === "customer" ? <ApplyForm onDone={reload} /> : (
        <p className="rounded-card bg-white p-6 text-muted">This account is a rider or admin account. Sign in with your kitchen&apos;s number instead.</p>
      )}
    </div>
  );
}

function ApplyForm({ onDone }: { onDone: () => Promise<void> }) {
  const adopt = useSession((s) => s.adopt);
  const [cities, setCities] = useState<City[]>([]);
  const [f, setF] = useState({ full_name: "", kitchen_name: "", city_code: "", street: "", area: "", zip: "", cuisines: "" });
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.core.GET("/api/v1/markets/cities").then((r) => {
      const list = unwrap(r) as City[];
      setCities(list);
      setF((x) => ({ ...x, city_code: x.city_code || list[0]?.code || "" }));
    }).catch(() => undefined);
  }, []);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.value }));
  function locate() {
    navigator.geolocation?.getCurrentPosition((p) => setPin({ lat: p.coords.latitude, lng: p.coords.longitude }), () => setError("We couldn't get your location; we'll use the city centre for now."));
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const city = cities.find((c) => c.code === f.city_code);
    try {
      const r = unwrap(await api.core.POST("/api/v1/restaurants/apply", { body: {
        full_name: f.full_name, kitchen_name: f.kitchen_name, city_code: f.city_code, street: f.street, area: f.area, zip: f.zip,
        cuisines: f.cuisines.split(",").map((c) => c.trim()).filter(Boolean), lat: pin?.lat ?? city!.lat, lng: pin?.lng ?? city!.lng } }));
      await adopt(r as { access_token: string; refresh_token: string });
      await onDone();
    } catch (err) {
      setError(errorMessage((err as { body?: unknown }).body, "Couldn't send your application. Try again."));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="grid gap-4 rounded-card bg-white p-6 sm:grid-cols-2" aria-label="Apply with your kitchen">
      <label className="text-sm font-bold">Your name<input required value={f.full_name} onChange={set("full_name")} className={input} /></label>
      <label className="text-sm font-bold">Kitchen name<input required value={f.kitchen_name} onChange={set("kitchen_name")} className={input} /></label>
      <label className="text-sm font-bold">City<select value={f.city_code} onChange={set("city_code")} className={input}>{cities.map((c) => <option key={c.code} value={c.code}>{c.name}, {c.region}</option>)}</select></label>
      <label className="text-sm font-bold">Area<input required value={f.area} onChange={set("area")} placeholder="e.g. Banjara Hills" className={input} /></label>
      <label className="text-sm font-bold sm:col-span-2">Street address<input required value={f.street} onChange={set("street")} className={input} /></label>
      <label className="text-sm font-bold">PIN / ZIP code<input required value={f.zip} onChange={set("zip")} className={input} /></label>
      <label className="text-sm font-bold">Cuisines<input required value={f.cuisines} onChange={set("cuisines")} placeholder="Andhra, Thali" className={input} /></label>
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="button" variant="secondary" onClick={locate}>{pin ? "Pin set at your location" : "I'm at the kitchen: use my location"}</Button>
        <span className="text-sm text-muted">{pin ? `${pin.lat.toFixed(4)}, ${pin.lng.toFixed(4)}` : "Otherwise we use the city centre and check the pin with you."}</span>
      </div>
      {error ? <p role="alert" className="text-sm font-semibold text-chili sm:col-span-2">{error}</p> : null}
      <div className="sm:col-span-2"><Button type="submit" size="lg" loading={busy}>Send application</Button></div>
    </form>
  );
}

function Steps({ app, onSaved }: { app: Application; onSaved: () => Promise<void> }) {
  const [fssai, setFssai] = useState({ number: "", until: "" });
  const [gstin, setGstin] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  async function save(fn: () => Promise<unknown>) {
    setMsg(null);
    try {
      await fn();
      await onSaved();
    } catch (err) {
      setMsg(errorMessage((err as { body?: unknown }).body));
    }
  }
  const rid = { params: { path: { restaurant_id: app.restaurant_id } } };
  return (
    <section className="space-y-4 rounded-card bg-white p-6" aria-label="Your application">
      <h2 className="font-display text-2xl font-semibold">{app.name} · {app.done} of {app.total} done</h2>
      <ol className="space-y-2">
        {app.steps.map((s, i) => (
          <li key={s.key} className="flex items-center gap-3">
            <span className={`flex h-7 w-7 items-center justify-center rounded-pill text-xs font-extrabold ${s.done ? "bg-peacock text-white" : "border-2 border-line-strong text-muted"}`}>{s.done ? "✓" : i + 1}</span>
            <b className="w-44">{s.title}</b><span className="text-sm text-muted">{s.detail}</span>
          </li>
        ))}
      </ol>
      {app.current === "fssai" ? (
        <div className="grid gap-3 rounded-card bg-porcelain p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <label className="text-sm font-bold">FSSAI licence number<input inputMode="numeric" value={fssai.number} onChange={(e) => setFssai({ ...fssai, number: e.target.value.replace(/\D/g, "").slice(0, 14) })} className={input} /></label>
          <label className="text-sm font-bold">Valid until<input type="date" value={fssai.until} onChange={(e) => setFssai({ ...fssai, until: e.target.value })} className={input} /></label>
          <Button disabled={fssai.number.length !== 14 || !fssai.until} onClick={() => void save(async () => unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/licence", { ...rid, body: { fssai_number: fssai.number, fssai_expires_on: fssai.until } })))}>Save licence</Button>
        </div>
      ) : null}
      {app.current === "gst_bank" ? (
        <div className="grid gap-3 rounded-card bg-porcelain p-4 sm:grid-cols-[1fr_auto] sm:items-end">
          <label className="text-sm font-bold">GSTIN<input value={gstin} maxLength={15} onChange={(e) => setGstin(e.target.value.toUpperCase())} className={input} /></label>
          <Button disabled={gstin.length !== 15} onClick={() => void save(async () => unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/gst", { ...rid, body: { gstin } })))}>Save GSTIN</Button>
        </div>
      ) : null}
      {msg ? <p role="alert" className="text-sm font-semibold text-chili">{msg}</p> : null}
      <p className="text-sm text-muted">Upload the licence certificate, add your bank and your menu in the BhojanGo Partner app on your kitchen tablet. We check everything and switch you on.</p>
    </section>
  );
}
