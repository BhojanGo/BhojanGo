"use client";
// Saved addresses (WebProfile): list, add, edit, delete, make default, with
// delivery notes. The map point comes from the areas Markets knows (the same
// search as the address box) or "use my location". Making one the default
// also makes it the address the site shows food for.

import { useEffect, useId, useRef, useState } from "react";

import { placeFromPoint } from "@/components/AddressBox";
import { Locate, Pin } from "@/components/Icons";
import { authed, urls } from "@/lib/client";
import { usePrefs, useT } from "@/lib/i18n";
import { card, ghost, h2, input, link, primary } from "./ui";

export interface Address {
  id: string;
  label: string | null;
  street: string;
  city: string;
  state: string | null;
  postal_code: string | null;
  country: string;
  lat: number | null;
  lng: number | null;
  is_default?: boolean;
  delivery_notes?: string | null;
}

interface Area {
  label: string;
  area: string;
  city_name: string;
  country: string;
  lat: number;
  lng: number;
}

interface Point {
  lat: number;
  lng: number;
  country: string;
  label: string;
  city?: string;
}

function AreaPicker({ point, onPoint }: { point: Point | null; onPoint: (p: Point) => void }) {
  const t = useT();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ q: string; list: Area[] } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const listId = useId();
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    clearTimeout(timer.current);
    const term = q.trim();
    if (term.length < 2) return;
    timer.current = setTimeout(async () => {
      try {
        const r = await fetch(`${urls.core}/api/v1/markets/areas?q=${encodeURIComponent(term)}`);
        const list = r.ok ? ((await r.json()) as Area[]) : [];
        setHits({ q: term, list });
        setProblem(list.length ? null : t("address.no_match"));
      } catch {
        setProblem(t("common.error"));
      }
    }, 200);
  }, [q, t]);

  function locate() {
    if (!navigator.geolocation) return setProblem(t("address.location_denied"));
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const p = await placeFromPoint(pos.coords.latitude, pos.coords.longitude);
          onPoint({ lat: p.lat, lng: p.lng, country: p.country, label: p.label });
          setProblem(null);
        } catch {
          setProblem(t("common.error"));
        } finally {
          setLocating(false);
        }
      },
      () => {
        setLocating(false);
        setProblem(t("address.location_denied"));
      },
      { timeout: 10000 },
    );
  }

  const shown = q.trim().length >= 2 && hits?.q === q.trim() ? hits.list : [];
  return (
    <div className="sm:col-span-2">
      <span className="text-sm font-bold text-[#4C5A5E]">{t("account.addresses.location")}</span>
      <p className="text-[13px] text-[#4C5A5E]">{t("account.addresses.location_hint")}</p>
      <div className="relative mt-2">
        <label className="flex h-11 items-center gap-2 rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-4 focus-within:border-[#0B5D66]">
          <Pin size={16} color="#0B5D66" />
          <span className="sr-only">{t("account.addresses.search_area")}</span>
          <input
            role="combobox"
            aria-expanded={shown.length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("account.addresses.search_area")}
            className="min-w-0 flex-grow bg-transparent text-[15px] text-[#111418] outline-none placeholder:text-[#4C5A5E]"
          />
        </label>
        {shown.length > 0 && (
          <ul id={listId} role="listbox" className="absolute left-0 right-0 top-[calc(100%+6px)] z-40 rounded-2xl border border-[#E2E7E8] bg-white p-2 shadow-[0_16px_40px_rgba(17,20,24,0.16)]">
            {shown.map((a) => (
              <li key={`${a.label}-${a.lat}-${a.lng}`} role="option" aria-selected={false}>
                <button
                  type="button"
                  onClick={() => {
                    onPoint({ lat: a.lat, lng: a.lng, country: a.country, label: a.label, city: a.city_name });
                    setQ("");
                  }}
                  className="flex h-11 w-full items-center gap-3 rounded-[10px] px-3 text-left font-semibold text-[#111418] hover:bg-[#EFF6F6]"
                >
                  <Pin size={16} color="#4C5A5E" />
                  {a.label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        <button type="button" onClick={locate} disabled={locating} className="inline-flex items-center gap-2 text-sm font-extrabold text-[#0B5D66] disabled:opacity-60">
          <Locate color="#0B5D66" />
          {locating ? t("address.locating") : t("address.use_my_location")}
        </button>
        {point && <span className="text-sm font-semibold text-[#24383B]">{t("account.addresses.location_set", { place: point.label })}</span>}
        {problem && <span role="status" className="text-sm text-[#4C5A5E]">{problem}</span>}
      </div>
    </div>
  );
}

function AddressForm({ address, onDone, onCancel }: { address: Address | null; onDone: () => void; onCancel: () => void }) {
  const t = useT();
  const [label, setLabel] = useState(address?.label ?? "");
  const [street, setStreet] = useState(address?.street ?? "");
  const [city, setCity] = useState(address?.city ?? "");
  const [state, setState] = useState(address?.state ?? "");
  const [postal, setPostal] = useState(address?.postal_code ?? "");
  const [notes, setNotes] = useState(address?.delivery_notes ?? "");
  const [point, setPoint] = useState<Point | null>(
    address && address.lat != null && address.lng != null ? { lat: address.lat, lng: address.lng, country: address.country, label: address.street } : null,
  );
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!point) return setProblem(t("account.addresses.location_needed"));
    setBusy(true);
    setProblem(null);
    const body = {
      label: label.trim() || undefined,
      street: street.trim(),
      city: city.trim(),
      state: state.trim(),
      postal_code: postal.trim(),
      country: point.country,
      lat: point.lat,
      lng: point.lng,
      delivery_notes: notes.trim() || null,
    };
    try {
      if (address) await authed("PATCH", `/api/v1/me/addresses/${address.id}`, body);
      else await authed("POST", "/api/v1/me/addresses", body);
      onDone();
    } catch (err) {
      setProblem(err instanceof Error && err.message && !err.message.startsWith("HTTP") ? err.message : t("account.profile.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} aria-label={address ? t("account.addresses.edit_title") : t("account.addresses.new_title")} className="mt-4 rounded-2xl border border-[#E2E7E8] bg-[#FAFBFB] p-4 md:p-5">
      <h3 className="font-bold">{address ? t("account.addresses.edit_title") : t("account.addresses.new_title")}</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <AreaPicker
          point={point}
          onPoint={(p) => {
            setPoint(p);
            if (p.city && !city.trim()) setCity(p.city);
          }}
        />
        <label className="text-sm font-bold text-[#4C5A5E]">
          {t("account.addresses.label")}
          <input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={50} className={input} />
        </label>
        <label className="text-sm font-bold text-[#4C5A5E]">
          {t("account.addresses.street")}
          <input value={street} onChange={(e) => setStreet(e.target.value)} required maxLength={500} autoComplete="street-address" className={input} />
        </label>
        <label className="text-sm font-bold text-[#4C5A5E]">
          {t("account.addresses.city")}
          <input value={city} onChange={(e) => setCity(e.target.value)} required maxLength={100} autoComplete="address-level2" className={input} />
        </label>
        <label className="text-sm font-bold text-[#4C5A5E]">
          {t("account.addresses.state")}
          <input value={state} onChange={(e) => setState(e.target.value)} required maxLength={100} autoComplete="address-level1" className={input} />
        </label>
        <label className="text-sm font-bold text-[#4C5A5E]">
          {t("account.addresses.postal_code")}
          <input value={postal} onChange={(e) => setPostal(e.target.value)} required maxLength={20} autoComplete="postal-code" className={input} />
        </label>
        <label className="text-sm font-bold text-[#4C5A5E] sm:col-span-2">
          {t("account.addresses.notes")}
          <input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} className={input} />
        </label>
      </div>
      {problem && <p role="alert" className="mt-3 text-sm font-semibold text-[#8C1D18]">{problem}</p>}
      <div className="mt-4 flex flex-wrap gap-[10px]">
        <button type="submit" disabled={busy} className={primary}>{t("common.save")}</button>
        <button type="button" onClick={onCancel} className={ghost}>{t("common.cancel")}</button>
      </div>
    </form>
  );
}

export function Addresses() {
  const t = useT();
  const { setPlace } = usePrefs();
  const [list, setList] = useState<Address[] | null | "error">(null);
  const [reload, setReload] = useState(0);
  const [editing, setEditing] = useState<Address | "new" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    authed<Address[]>("GET", "/api/v1/me/addresses")
      .then((r) => live && setList(r))
      .catch(() => live && setList("error"));
    return () => {
      live = false;
    };
  }, [reload]);

  const refresh = () => setReload((n) => n + 1);

  async function makeDefault(a: Address) {
    setProblem(null);
    try {
      await authed("POST", `/api/v1/me/addresses/${a.id}/default`);
      refresh();
      // The site follows your default address (kitchens, country, prices).
      if (a.lat != null && a.lng != null) {
        const p = await placeFromPoint(a.lat, a.lng, [a.label, a.street].filter(Boolean).join(" · "));
        setPlace({ ...p, address_id: a.id });
      }
    } catch {
      setProblem(t("account.profile.save_failed"));
    }
  }

  async function remove(a: Address) {
    if (!window.confirm(t("account.addresses.confirm_delete", { label: a.label || a.street }))) return;
    setProblem(null);
    try {
      await authed("DELETE", `/api/v1/me/addresses/${a.id}`);
      refresh();
    } catch {
      setProblem(t("account.profile.save_failed"));
    }
  }

  const items = Array.isArray(list) ? list : [];
  return (
    <section id="addresses" aria-labelledby="addresses-title" className={card}>
      <h2 id="addresses-title" className={h2}>{t("account.addresses.title")}</h2>
      {list === null && <p role="status" className="mt-3 text-[#4C5A5E]">{t("account.loading")}</p>}
      {list === "error" && <p className="mt-3 text-[#4C5A5E]">{t("account.addresses.unavailable")}</p>}
      {list !== null && list !== "error" && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((a) => (
            <div key={a.id} className={`flex flex-col rounded-2xl p-4 ${a.is_default ? "bg-[#EFF6F6] shadow-[inset_0_0_0_1.5px_#0B5D66]" : "border border-[#E2E7E8]"}`}>
              <div className="flex items-baseline justify-between gap-2">
                <b className="truncate">{a.label || a.street}</b>
                {a.is_default ? (
                  <span className="shrink-0 text-xs font-extrabold uppercase text-[#083F46]">{t("account.addresses.default")}</span>
                ) : (
                  <button type="button" onClick={() => void makeDefault(a)} className={`${link} text-[13px]`}>{t("account.addresses.make_default")}</button>
                )}
              </div>
              <div className="mt-1 text-sm text-[#24383B]">{[a.street, a.city, a.state].filter(Boolean).join(", ")} {a.postal_code}</div>
              {a.delivery_notes && <div className="mt-1 text-[13px] text-[#4C5A5E]">{a.delivery_notes}</div>}
              <div className="mt-auto flex gap-4 pt-3 text-[13px]">
                <button type="button" onClick={() => setEditing(a)} className={link}>{t("account.addresses.edit")}</button>
                <button type="button" onClick={() => void remove(a)} className="font-bold text-[#B3261E]">{t("account.addresses.delete")}</button>
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setEditing("new")}
            aria-expanded={editing === "new"}
            className="flex min-h-[110px] items-center justify-center rounded-2xl border-[1.5px] border-dashed border-[#C9D3D4] p-4 font-extrabold text-[#0B5D66] hover:bg-[#F4F6F6]"
          >
            + {t("account.addresses.add")}
          </button>
        </div>
      )}
      {problem && <p role="alert" className="mt-3 text-sm font-semibold text-[#8C1D18]">{problem}</p>}
      {editing && (
        <AddressForm
          key={editing === "new" ? "new" : editing.id}
          address={editing === "new" ? null : editing}
          onCancel={() => setEditing(null)}
          onDone={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
    </section>
  );
}
