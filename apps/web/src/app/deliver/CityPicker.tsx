"use client";
// The city whose pay the page shows (the country's live cities, from the API).
// Changing it reloads the page for ?city=<code> (the server prices it).
import { useRouter } from "next/navigation";
import { useId, useTransition } from "react";

import { Chevron } from "@/components/Icons";

export function CityPicker({ cities, value, label }: { cities: { code: string; name: string; region: string }[]; value: string; label: string }) {
  const router = useRouter();
  const id = useId();
  const [pending, start] = useTransition();
  return (
    <div className="flex items-center gap-3">
      <label htmlFor={id} className="text-label text-muted">{label}</label>
      <span className="relative inline-flex">
        <select
          id={id}
          data-testid="city-picker"
          value={value}
          aria-busy={pending}
          onChange={(e) => start(() => router.push(`/deliver?city=${encodeURIComponent(e.target.value)}#pay`, { scroll: false }))}
          className="h-12 min-w-[200px] appearance-none rounded-[14px] border-[1.5px] border-line-strong bg-white pl-4 pr-10 text-label text-kohl focus:border-peacock focus:outline-none focus:ring-2 focus:ring-peacock/30"
        >
          {cities.map((c) => (
            <option key={c.code} value={c.code}>{`${c.name}, ${c.region}`}</option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2"><Chevron color="#4C5A5E" /></span>
      </span>
    </div>
  );
}
