"use client";
// "Where we deliver": countries -> states -> cities from Markets, with country
// tabs and a city search (filtered in the browser). Two looks from the design:
// the landing block (WebLanding: underline tabs, one card per country, city
// chips) and the full directory (WebCities: pill tabs, a card per city).

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type MouseEvent, useId, useMemo, useState } from "react";

import { Search } from "@/components/Icons";
import { libraryPhoto, photo } from "@/lib/format";
import { waitingOf } from "@/lib/contract";
import { useFormat, useLanguage, usePrefs, useT } from "@/lib/i18n";
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
    <label id={anchor} htmlFor={id} className={`flex scroll-mt-[120px] items-center gap-[10px] rounded-full border border-[#E2E7E8] bg-[#F4F6F6] px-[18px] text-body focus-within:border-[#0B5D66] ${className}`}>
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
      <Waiting c={c} className="text-small text-[#7A4F0E]" />
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
          <h2 id="where-we-deliver" className="m-0 text-h1 tracking-[-0.8px]">{t("cities.title")}</h2>
          <p className="mt-[6px] text-body text-[#4C5A5E]">{totalsLine(t, dir.totals)}</p>
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
              className={`flex h-11 shrink-0 items-center px-4 ${on ? "border-b-[2.5px] border-[#0B5D66] font-bold text-[#083F46]" : "font-bold text-[#4C5A5E]"}`}
            >
              {tab.label}
              {tab.count != null && <span className="ml-[6px] rounded-md bg-[#F4F6F6] px-[6px] py-[2px] text-small">{tab.count}</span>}
            </button>
          );
        })}
      </div>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {shown.map((k) => (
          <div key={k.code} className="rounded-[24px] border border-[#E2E7E8] p-6">
            <div className="text-caption text-[#4C5A5E]">{k.name}</div>
            {k.regions.map((r) => (
              <div key={r.code}>
                <div className="mt-4 text-label text-[#4C5A5E]">{r.name}</div>
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
    <p role="status" className="text-body text-[#4C5A5E] md:col-span-2">
      {t("cities.no_match")}{" "}
      <a href="#suggest" className="font-bold">
        {t("cities.suggest_link")}
      </a>
    </p>
  );
}

/** "Change city" (/cities?choose=1): picking a city remembers it and goes home. */
export interface Choosing {
  addressCity: string | null;
}

/**
 * A city card (WebCities). The photo: the city's first kitchen's cover when it is
 * live, else its country's hero dish (Markets data), never an empty box. Coming soon:
 * "Coming soon · N people waiting" from the Notify-me list (the directory's count).
 */
function CityCard({ c, region, cover, country, choosing }: { c: DirCity; region: string; cover: string | null; country: DirCountry; choosing?: Choosing | null }) {
  const t = useT();
  const f = useFormat();
  const router = useRouter();
  const { language } = useLanguage();
  const { setCity } = usePrefs();
  const live = c.status === "live";
  const img = photo(cover, 400) ?? libraryPhoto(country.hero_photo, 400);
  const waiting = waitingOf(c);
  const status = live
    ? t("cities.kitchens", { count: c.restaurants })
    : [t("common.coming_soon"), waiting > 0 ? t("common.people_waiting", { count: waiting, n: f.number(waiting) }) : null].filter(Boolean).join(" · ");
  const pick = choosing
    ? (e: MouseEvent) => {
        e.preventDefault();
        setCity({ code: c.code, locales: country.locales ?? [] }, { language, addressCity: choosing.addressCity });
        router.push("/");
        router.refresh();
      }
    : undefined;
  const notify = !live && !choosing;
  return (
    <Link
      href={choosing ? "/" : c.path}
      onClick={pick}
      data-city={c.code}
      data-status={c.status}
      className="flex min-w-0 items-center gap-[14px] rounded-[18px] border border-[#E2E7E8] p-[14px] text-[#111418] hover:border-[#C9D3D4] hover:text-[#111418]"
    >
      {img ? (
        <span className="block h-[72px] w-[72px] shrink-0 overflow-hidden rounded-[14px] bg-[#EFF6F6]">
          {/* eslint-disable-next-line @next/next/no-img-element -- local WebP sizes from the photo library */}
          <img src={img} alt="" loading="lazy" className="block h-full w-full object-cover" />
        </span>
      ) : null}
      <span className="min-w-0 flex-1">
        <b className="block break-words text-h3">{c.name}</b>
        <span className="block break-words text-small text-[#4C5A5E]">{region}</span>
        <span data-testid="city-status" className={`mt-1 block text-label ${live ? "text-[#0B5D66]" : "text-[#7A4F0E]"}`}>{status}</span>
        {notify && (
          <span className="mt-2 inline-flex h-10 items-center rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-4 text-label text-[#111418] sm:hidden">
            {t("notify.button")}
          </span>
        )}
      </span>
      {notify && (
        <span className="hidden h-10 shrink-0 items-center whitespace-nowrap rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-4 text-label text-[#111418] sm:inline-flex">
          {t("notify.button")}
        </span>
      )}
    </Link>
  );
}

function CityGrid({ k, covers, choosing }: { k: DirCountry; covers: Record<string, string | null>; choosing?: Choosing | null }) {
  return (
    <>
      {k.regions.map((r, i) => (
        <div key={r.code}>
          <h3 className={`m-0 text-label ${i ? "mt-[22px]" : "mt-[14px]"}`}>{r.name}</h3>
          <div className="mt-[10px] grid grid-cols-1 gap-[14px] md:grid-cols-2 lg:grid-cols-3">
            {r.cities.map((c) => (
              <CityCard key={c.code} c={c} region={r.name} cover={covers[c.code] ?? null} country={k} choosing={choosing} />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

/**
 * "Change city" (R8): the visitor's country's cities only, with a search that
 * filters as you type (city or state); every other country behind "Other
 * countries" (opened by itself when only another country matches the search).
 */
export function ChooseCity({ dir, covers, country, choosing }: { dir: Directory; covers: Record<string, string | null>; country: string | null; choosing: Choosing }) {
  const t = useT();
  const [q, setQ] = useState("");
  const [othersOpen, setOthersOpen] = useState(false);
  const shown = useFiltered(dir, "all", q);
  const home = shown.find((k) => k.code === country) ?? null;
  const others = shown.filter((k) => k.code !== country);
  const homeName = dir.countries.find((k) => k.code === country)?.name ?? null;
  const open = othersOpen || (!!q.trim() && !home && others.length > 0) || !country;
  return (
    <>
      <div className="mt-6">
        <SearchField anchor="search" value={q} onChange={setQ} placeholder={t("cities.search")} className="h-[52px] w-full md:w-[480px]" />
      </div>
      {home ? (
        <section aria-label={home.name} data-testid="choose-home" data-country={home.code} className="pt-8">
          <h2 className="m-0 text-caption text-[#4C5A5E]">{home.name}</h2>
          <CityGrid k={home} covers={covers} choosing={choosing} />
        </section>
      ) : (
        country && (
          <p role="status" className="pt-8 text-body text-[#4C5A5E]">
            {homeName && q.trim() ? t("cities.no_match_in", { country: homeName }) : t("cities.no_match")}
          </p>
        )
      )}
      {(others.length > 0 || !q.trim()) && dir.countries.some((k) => k.code !== country) && (
        <details
          data-testid="other-countries"
          open={open}
          onToggle={(e) => setOthersOpen((e.currentTarget as HTMLDetailsElement).open)}
          className="mt-10 border-t border-[#E2E7E8] pt-6"
        >
          <summary className="inline-flex min-h-11 cursor-pointer items-center text-label text-[#0B5D66]">
            {country ? t("cities.other_countries") : t("cities.all_countries")}
          </summary>
          {others.map((k) => (
            <section key={k.code} aria-label={k.name} className="pt-6">
              <h2 className="m-0 text-caption text-[#4C5A5E]">{k.name}</h2>
              <CityGrid k={k} covers={covers} choosing={choosing} />
            </section>
          ))}
        </details>
      )}
      {!home && !others.length && q.trim() && (
        <div className="pt-6">
          <NoMatch />
        </div>
      )}
    </>
  );
}

/** The full directory (WebCities). */
export function CitiesDirectory({ dir, covers, choosing }: { dir: Directory; covers: Record<string, string | null>; choosing?: Choosing | null }) {
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
                className={`inline-flex h-10 shrink-0 items-center rounded-full px-4 text-label ${on ? "bg-[#111418] text-white" : "border border-[#C9D3D4] text-[#111418]"}`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>
      {shown.map((k) => (
        <section key={k.code} aria-label={k.name} className="pt-10">
          <h2 className="m-0 text-caption text-[#4C5A5E]">{k.name}</h2>
          <CityGrid k={k} covers={covers} choosing={choosing} />
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
