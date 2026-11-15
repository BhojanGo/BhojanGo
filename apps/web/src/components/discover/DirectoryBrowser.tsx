"use client";
// "Where we deliver": countries -> states -> cities from Markets, with country
// tabs and a city search (filtered in the browser). Two looks from the design:
// the landing block (WebLanding: underline tabs, one card per country, city
// chips) and the full directory (WebCities: pill tabs, a card per city).

import Link from "next/link";
import { useId, useMemo, useState } from "react";

import { Search } from "@/components/Icons";
import { photo } from "@/lib/format";
import { waitingOf } from "@/lib/contract";
import { useFormat, useT } from "@/lib/i18n";
import type { DirCity, DirCountry, Directory } from "@/lib/server";
import { totalsLine } from "./places";

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

type Filter = "all" | "live" | string; // a country code

function useFiltered(dir: Directory, filter: Filter, q: string) {
  return useMemo(() => {
    const needle = norm(q.trim());
    return dir.countries
      .filter((k) => filter === "all" || filter === "live" || k.code === filter)
      .map((k) => ({
        ...k,
        regions: k.regions
          .map((r) => ({
            ...r,
            cities: r.cities.filter(
              (c) => (filter !== "live" || c.status === "live") && (!needle || norm(c.name).includes(needle) || norm(r.name).includes(needle) || norm(k.name).includes(needle)),
            ),
          }))
          .filter((r) => r.cities.length),
      }))
      .filter((k) => k.regions.length);
  }, [dir, filter, q]);
}

function SearchField({ value, onChange, placeholder, className, anchor }: { value: string; onChange: (v: string) => void; placeholder: string; className: string; anchor?: string }) {
  const id = useId();
  return (
    <label id={anchor} htmlFor={id} className={`flex scroll-mt-[120px] items-center gap-[10px] rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-[18px] text-[15px] focus-within:border-[#0B5D66] ${className}`}>
      <Search size={18} color="#4C5A5E" />
      <span className="sr-only">{placeholder}</span>
      <input id={id} type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="min-w-0 flex-grow bg-transparent text-[#111418] outline-none placeholder:text-[#4C5A5E]" />
    </label>
  );
}

/** "12 people waiting" for a coming-soon city (nothing when 0 or unknown). */
function Waiting({ c, className }: { c: DirCity; className?: string }) {
  const t = useT();
  const f = useFormat();
  const n = waitingOf(c);
  return n > 0 ? <span className={className}>{t("common.people_waiting", { count: n, n: f.number(n) })}</span> : null;
}

function CityChip({ c }: { c: DirCity }) {
  const t = useT();
  return c.status === "live" ? (
    <Link href={c.path} className="flex h-11 items-center gap-2 rounded-full border border-[#DDEBEC] bg-[#EFF6F6] px-4 font-bold text-[#083F46] hover:text-[#083F46]">
      <span aria-hidden="true" className="h-2 w-2 rounded-full bg-[#0B5D66]" />
      {c.name}
    </Link>
  ) : (
    <Link href={c.path} className="flex h-11 items-center gap-2 rounded-full border border-dashed border-[#C9D3D4] px-4 font-semibold text-[#4C5A5E] hover:text-[#111418]">
      {c.name} · {t("common.soon")}
      <Waiting c={c} className="text-xs font-bold text-[#7A4F0E]" />
    </Link>
  );
}

/** The landing page's block (WebLanding "Where we deliver"). */
export function LandingDirectory({ dir }: { dir: Directory }) {
  const t = useT();
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const shown = useFiltered(dir, filter, q);
  const tabs: { key: Filter; label: string; count?: number }[] = [
    { key: "all", label: t("cities.all_countries") },
    ...dir.countries.map((k) => ({ key: k.code, label: k.name, count: k.live + k.soon })),
  ];
  return (
    <section aria-labelledby="where-we-deliver" className="mx-auto max-w-[1440px] px-5 pt-14 md:px-16 md:pt-20">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 id="where-we-deliver" className="m-0 font-display text-[28px] font-semibold tracking-[-0.8px] md:text-[36px]">{t("cities.title")}</h2>
          <p className="mt-[6px] text-base text-[#4C5A5E]">{totalsLine(t, dir.totals)}</p>
        </div>
        <SearchField value={q} onChange={setQ} placeholder={t("home.find_your_city")} className="h-12 w-full md:w-[360px]" />
      </div>
      <div role="tablist" aria-label={t("cities.countries")} className="mt-6 flex gap-2 overflow-x-auto border-b border-[#E2E7E8]">
        {tabs.map((tab) => {
          const on = filter === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setFilter(tab.key)}
              className={`flex h-11 shrink-0 items-center px-4 ${on ? "border-b-[2.5px] border-[#0B5D66] font-extrabold text-[#083F46]" : "font-bold text-[#4C5A5E]"}`}
            >
              {tab.label}
              {tab.count != null && <span className="ml-[6px] rounded-md bg-[#F4F6F6] px-[6px] py-[2px] text-xs">{tab.count}</span>}
            </button>
          );
        })}
      </div>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {shown.map((k) => (
          <div key={k.code} className="rounded-[24px] border border-[#E2E7E8] p-6">
            <div className="text-[13px] font-extrabold uppercase tracking-[1px] text-[#4C5A5E]">{k.name}</div>
            {k.regions.map((r) => (
              <div key={r.code}>
                <div className="mt-4 text-sm font-bold text-[#4C5A5E]">{r.name}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {r.cities.map((c) => (
                    <CityChip key={c.code} c={c} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ))}
        {!shown.length && <NoMatch />}
      </div>
    </section>
  );
}

function NoMatch() {
  const t = useT();
  return (
    <p role="status" className="text-[15px] text-[#4C5A5E] md:col-span-2">
      {t("cities.no_match")}{" "}
      <a href="#suggest" className="font-bold">
        {t("cities.suggest_link")}
      </a>
    </p>
  );
}

function CityCard({ c, region, cover }: { c: DirCity; region: string; cover: string | null }) {
  const t = useT();
  const live = c.status === "live";
  const img = photo(cover, 400);
  return (
    <Link href={c.path} className={`flex items-center gap-[14px] rounded-[18px] border border-[#E2E7E8] p-[14px] text-[#111418] hover:border-[#C9D3D4] hover:text-[#111418] ${live ? "" : "opacity-90"}`}>
      <span className={`block h-[72px] w-[72px] shrink-0 overflow-hidden rounded-[14px] bg-[#EFF6F6] ${live ? "" : "grayscale-[0.6]"}`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
        {img && <img src={img} alt="" loading="lazy" className="block h-full w-full object-cover" />}
      </span>
      <span className="min-w-0 flex-grow">
        <b className="block text-[17px]">{c.name}</b>
        <span className="block text-sm text-[#4C5A5E]">{region}</span>
        <span className={`mt-1 block text-[13px] font-bold ${live ? "text-[#0B5D66]" : "text-[#4C5A5E]"}`}>
          {live ? t("cities.kitchens", { count: c.restaurants }) : t("common.coming_soon")}
        </span>
        {!live && <Waiting c={c} className="block text-[13px] text-[#7A4F0E]" />}
      </span>
      {!live && (
        <span className="inline-flex h-10 shrink-0 items-center whitespace-nowrap rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-4 text-[15px] font-extrabold text-[#111418]">
          {t("notify.button")}
        </span>
      )}
    </Link>
  );
}

/** The full directory (WebCities). */
export function CitiesDirectory({ dir, covers }: { dir: Directory; covers: Record<string, string | null> }) {
  const t = useT();
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const shown = useFiltered(dir, filter, q);
  const tabs: { key: Filter; label: string }[] = [
    { key: "all", label: t("cities.all_countries") },
    ...dir.countries.map((k: DirCountry) => ({ key: k.code, label: t("cities.country_live", { country: k.name, count: k.live }) })),
    { key: "live", label: t("cities.live_now") },
  ];
  return (
    <>
      <div className="mt-6 flex flex-col gap-4 md:flex-row md:items-center">
        <SearchField anchor="search" value={q} onChange={setQ} placeholder={t("cities.search")} className="h-[52px] w-full md:w-[480px]" />
        <div role="group" aria-label={t("cities.countries")} className="flex gap-2 overflow-x-auto pb-1 md:gap-4 md:pb-0">
          {tabs.map((tab) => {
            const on = filter === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                aria-pressed={on}
                onClick={() => setFilter(tab.key)}
                className={`inline-flex h-10 shrink-0 items-center rounded-full px-4 text-sm font-bold ${on ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"}`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>
      {shown.map((k) => (
        <section key={k.code} aria-label={k.name} className="pt-10">
          <h2 className="m-0 text-xs font-extrabold uppercase tracking-[1px] text-[#4C5A5E]">{k.name}</h2>
          {k.regions.map((r, i) => (
            <div key={r.code}>
              <h3 className={`m-0 text-[15px] font-extrabold ${i ? "mt-[22px]" : "mt-[14px]"}`}>{r.name}</h3>
              <div className="mt-[10px] grid gap-[14px] md:grid-cols-2 lg:grid-cols-3">
                {r.cities.map((c) => (
                  <CityCard key={c.code} c={c} region={r.name} cover={covers[c.code] ?? null} />
                ))}
              </div>
            </div>
          ))}
        </section>
      ))}
      {!shown.length && (
        <div className="pt-10">
          <NoMatch />
        </div>
      )}
    </>
  );
}
