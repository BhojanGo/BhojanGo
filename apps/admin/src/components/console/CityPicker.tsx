"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import type { CountrySummary, MarketStatus } from "@/lib/markets";

const DOT: Record<MarketStatus, string> = {
  live: "bg-peacock",
  beta: "bg-kesar",
  paused: "bg-danger",
  draft: "border-2 border-dashed border-muted",
};

/** Searchable city picker grouped by state (design board: scope bar). */
export function CityPicker({
  country,
  value,
  onChange,
}: {
  country: CountrySummary;
  value: string | null;
  onChange: (cityCode: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const all = useMemo(
    () => country.regions.flatMap((r) => r.cities.map((c) => ({ ...c, regionName: r.name }))),
    [country]
  );
  const selected = all.find((c) => c.code === value);
  const matches = all.filter(
    (c) => !query || c.name.toLowerCase().includes(query.toLowerCase()) || c.regionName.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  function choose(code: string) {
    setOpen(false);
    setQuery("");
    onChange(code);
  }

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 min-w-[200px] items-center gap-2 rounded-[10px] border-[1.5px] border-peacock bg-white px-3 text-sm font-bold text-kohl"
      >
        {selected ? <span className={`h-2 w-2 rounded-full ${DOT[selected.status]}`} /> : null}
        <span className="flex-grow text-left">{selected ? selected.name : "Pick a city"}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 z-[1000] mt-2 w-72 rounded-2xl border border-line bg-white p-2 shadow-[0_8px_24px_rgba(17,20,24,0.12)]">
          <label className="flex h-10 items-center gap-2 rounded-full bg-porcelain px-3">
            <span className="sr-only">Search cities</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4C5A5E" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              ref={inputRef}
              role="combobox"
              aria-controls={listId}
              aria-expanded="true"
              aria-activedescendant={matches[active] ? `${listId}-${matches[active].code}` : undefined}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, matches.length - 1));
                else if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
                else if (e.key === "Enter" && matches[active]) choose(matches[active].code);
                else if (e.key === "Escape") setOpen(false);
              }}
              placeholder={`Search cities in ${country.name}`}
              className="w-full border-0 bg-transparent text-sm outline-none"
            />
          </label>
          <ul id={listId} role="listbox" aria-label="Cities" className="mt-2 max-h-72 overflow-y-auto">
            {matches.length === 0 && <li className="px-3 py-2 text-sm text-muted">No city matches</li>}
            {matches.map((c, i) => {
              // A state's name above its first city.
              const header = i === 0 || c.regionName !== matches[i - 1]?.regionName ? c.regionName : null;
              return (
                <li key={c.code} role="presentation">
                  {header && <div className="px-3 pb-1 pt-2 text-xs font-bold uppercase tracking-wide text-muted">{header}</div>}
                  <div
                    id={`${listId}-${c.code}`}
                    role="option"
                    aria-selected={c.code === value}
                    tabIndex={-1}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => choose(c.code)}
                    onKeyDown={(e) => e.key === "Enter" && choose(c.code)}
                    className={`flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm ${i === active ? "bg-peacock-wash" : ""}`}
                  >
                    <span className={`h-2 w-2 rounded-full ${DOT[c.status]}`} />
                    <span className="flex-grow font-semibold">{c.name}</span>
                    <span className="text-xs capitalize text-muted">{c.status}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
