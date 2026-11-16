"use client";
// The delivery address box (landing hero, address sheet). Typing searches the
// areas Markets knows (/markets/areas: no paid geocoder); "Use my location" asks
// the browser, only when tapped. Picking a place sets the address cookie: the
// home page becomes the personal home, or "Not in your area yet".

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { urls } from "@/lib/client";
import { setCookie, useT } from "@/lib/i18n";
import type { Place } from "@/lib/prefs";
import { Locate, Pin } from "./Icons";

interface Area {
  label: string;
  area: string;
  city_code: string;
  city_name: string;
  city_path: string;
  country: string;
  lat: number;
  lng: number;
  served: boolean;
}

export async function placeFromPoint(lat: number, lng: number, label?: string): Promise<Place> {
  const r = await fetch(`${urls.core}/api/v1/markets/locate?lat=${lat}&lng=${lng}`);
  const loc = (await r.json()) as { serviceable: boolean; country_code?: string; city_code?: string; city_name?: string; zone_name?: string };
  const d = (await (await fetch(`${urls.core}/api/v1/markets/directory`)).json()) as {
    countries: { code: string; regions: { cities: { code: string; path: string }[] }[] }[];
  };
  const city = d.countries.flatMap((k) => k.regions.flatMap((r) => r.cities.map((c) => ({ ...c, country: k.code })))).find((c) => c.code === loc.city_code);
  return {
    label: label ?? ([loc.zone_name, loc.city_name].filter(Boolean).join(", ") || `${lat.toFixed(4)}, ${lng.toFixed(4)}`),
    lat,
    lng,
    country: loc.country_code ?? city?.country ?? "",
    city_code: loc.city_code ?? null,
    city_path: city?.path ?? null,
    zone: loc.zone_name ?? null,
    served: loc.serviceable,
  };
}

/** Save the place and go home (personal home, or "not in your area"). */
export function usePickPlace() {
  const router = useRouter();
  return (p: Place, to = "/") => {
    setCookie("bg_addr", JSON.stringify(p));
    router.push(to);
    router.refresh();
  };
}

/** "Use my location": the browser's position, only when the visitor asks. */
export function useMyLocation(onProblem: (m: string | null) => void, onPicked?: () => void) {
  const t = useT();
  const pick = usePickPlace();
  const [busy, setBusy] = useState(false);
  function run() {
    if (!navigator.geolocation) return onProblem(t("address.location_denied"));
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          pick(await placeFromPoint(pos.coords.latitude, pos.coords.longitude));
          onPicked?.();
        } catch {
          onProblem(t("common.error"));
        } finally {
          setBusy(false);
        }
      },
      () => {
        setBusy(false);
        onProblem(t("address.location_denied"));
      },
      { timeout: 10000 },
    );
  }
  return { run, busy };
}

export function AddressBox({
  size = "hero",
  country,
  autoFocus,
  onPicked,
}: {
  size?: "hero" | "sheet";
  country?: string | null;
  autoFocus?: boolean;
  /** Called once a place is chosen (a sheet or dialog closes itself). */
  onPicked?: () => void;
}) {
  const t = useT();
  const pick = usePickPlace();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Area[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const locate = useMyLocation(setProblem, onPicked);
  const listId = useId();
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    clearTimeout(timer.current);
    if (q.trim().length < 2) return;
    timer.current = setTimeout(async () => {
      try {
        const r = await fetch(`${urls.core}/api/v1/markets/areas?q=${encodeURIComponent(q.trim())}`);
        const list = r.ok ? ((await r.json()) as Area[]) : [];
        // the visitor's country first
        setHits([...list.filter((a) => a.country === country), ...list.filter((a) => a.country !== country)]);
        setActive(0);
        setProblem(list.length ? null : t("address.no_match"));
      } catch {
        setProblem(t("common.error"));
      }
    }, 200);
  }, [q, country, t]);

  const choose = (a: Area) => {
    pick({ label: a.label, lat: a.lat, lng: a.lng, country: a.country, city_code: a.city_code, city_path: a.city_path, zone: a.served ? a.area : null, served: a.served });
    setQ("");
    onPicked?.();
  };

  const hero = size === "hero";
  const shown = q.trim().length >= 2 ? hits : [];
  return (
    <div className="relative">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          const hit = shown[active];
          if (hit) choose(hit);
        }}
        className={
          hero
            ? // A phone: the field full width, the button under it (the placeholder is never cut); from 640 px one pill.
              "flex max-w-[660px] flex-col gap-3 sm:h-[60px] sm:flex-row sm:items-center sm:rounded-full sm:border sm:border-[#DDEBEC] sm:bg-white sm:pl-5 sm:pr-2 sm:shadow-[0_1px_2px_rgba(17,20,24,0.06),0_12px_32px_rgba(11,93,102,0.14)] md:h-[72px] md:pl-[26px]"
            : "flex h-[52px] items-center gap-3 rounded-full border border-[#E2E7E8] bg-[#F4F6F6] pl-4 pr-2"
        }
      >
        <div
          className={
            hero
              ? "flex h-14 min-w-0 flex-grow items-center gap-3 rounded-full border border-[#DDEBEC] bg-white pl-5 pr-4 shadow-[0_1px_2px_rgba(17,20,24,0.06),0_12px_32px_rgba(11,93,102,0.14)] sm:h-auto sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"
              : "contents"
          }
        >
        <Pin size={22} color="#0B5D66" />
        <input
          aria-label={t("address.label")}
          role="combobox"
          aria-expanded={shown.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          autoFocus={autoFocus}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setActive((i) => Math.min(i + 1, shown.length - 1));
            if (e.key === "ArrowUp") setActive((i) => Math.max(i - 1, 0));
          }}
          placeholder={t("address.placeholder")}
          className="min-w-0 flex-grow bg-transparent text-body-lg text-[#111418] outline-none placeholder:text-muted"
        />
        </div>
        <button
          type="submit"
          className={`shrink-0 rounded-full border-0 bg-[#0B5D66] text-label text-white hover:bg-[#083F46] ${hero ? "h-12 w-full px-5 sm:h-11 sm:w-auto md:h-14 md:px-[30px]" : "h-10 px-4"}`}
        >
          {t("address.find_food")}
        </button>
      </form>
      {shown.length > 0 && (
        <ul id={listId} role="listbox" className="absolute left-0 right-0 top-[calc(100%+8px)] z-40 max-w-[660px] rounded-2xl border border-[#E2E7E8] bg-white p-2 shadow-[0_16px_40px_rgba(17,20,24,0.16)]">
          {shown.map((a, i) => (
            <li key={`${a.city_code}-${a.label}`} role="option" aria-selected={i === active}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(a)}
                className={`flex h-12 w-full items-center gap-3 rounded-[10px] px-3 text-left ${i === active ? "bg-[#EFF6F6]" : ""}`}
              >
                <Pin size={16} color="#3D4A4E" />
                <span className="flex-grow font-semibold text-[#111418]">{a.label}</span>
                <span className={`text-small ${a.served ? "text-[#0B5D66]" : "text-muted"}`}>
                  {a.served ? t("address.served") : t("address.not_served")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {(!hero || problem) && (
        <div className="mt-2 flex items-center gap-2">
          {!hero && (
            <button type="button" onClick={locate.run} disabled={locate.busy} className="inline-flex items-center gap-2 text-label text-[#0B5D66] disabled:opacity-60">
              <Locate color="#0B5D66" />
              {locate.busy ? t("address.locating") : t("address.use_my_location")}
            </button>
          )}
          {problem && <span role="status" className="text-small text-muted">{problem}</span>}
        </div>
      )}
    </div>
  );
}
