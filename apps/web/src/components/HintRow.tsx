"use client";
// The IP hint (GET /markets/hint, asked from the browser so it's the visitor's IP,
// not the server's) and "Use my location" under the landing page's address box.
// The hint is evidence only (R8): its country (bg_hint) and its own town
// (bg_hint_place: "Meridian", "ID", served or not) go into cookies, and the server's
// location line shows that town as itself, unless an address or a chosen city wins.

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { urls } from "@/lib/client";
import { setCookie, useT } from "@/lib/i18n";
import { useMyLocation } from "./AddressBox";
import { Locate } from "./Icons";

interface Hint {
  country: string | null;
  place: string | null;
  region: string | null;
  region_code?: string | null;
  city_code: string | null;
  city_name: string | null;
  city_path: string | null;
  served: boolean;
}

const CACHE = "bg_hint_v2";

function readCookie(name: string): string | null {
  const hit = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : null;
}

/** The cookie values for a hint (what the server's getContext reads). */
export function hintCookies(h: Hint): { country: string | null; place: string | null } {
  if (!h.country) return { country: null, place: null };
  const place = h.place
    ? JSON.stringify({ place: h.place, region_code: h.region_code ?? null, city_code: h.served ? h.city_code : null, served: !!h.served })
    : null;
  return { country: h.country, place };
}

export function HintRow({ currentCountry, countrySource, hintSource }: { currentCountry: string | null; countrySource: string; hintSource: string }) {
  const t = useT();
  const router = useRouter();
  const [problem, setProblem] = useState<string | null>(null);
  const locate = useMyLocation(setProblem);

  useEffect(() => {
    let cached: Hint | null = null;
    try {
      cached = JSON.parse(sessionStorage.getItem(CACHE) ?? "null");
    } catch {
      /* private mode */
    }
    const apply = (h: Hint) => {
      const next = hintCookies(h);
      const changed = readCookie("bg_hint") !== next.country || readCookie("bg_hint_place") !== next.place;
      if (!changed) return;
      setCookie("bg_hint", next.country);
      setCookie("bg_hint_place", next.place);
      setCookie("bg_hint_city", null); // R6's cookie, replaced by bg_hint_place
      // Re-render only where the hint decides something: the country (when nothing
      // stronger did) or the location line (when no address or chosen city did).
      const countryOpen = countrySource === "browser" || countrySource === "default" || countrySource === "none" || countrySource === "ip";
      const lineOpen = hintSource === "ip" || hintSource === "none";
      if ((countryOpen && next.country !== currentCountry) || lineOpen) router.refresh();
    };
    if (cached) return apply(cached);
    fetch(`${urls.core}/api/v1/markets/hint`)
      .then((r) => (r.ok ? r.json() : null))
      .then((h: Hint | null) => {
        if (!h) return;
        try {
          sessionStorage.setItem(CACHE, JSON.stringify(h));
        } catch {
          /* private mode */
        }
        apply(h);
      })
      .catch(() => undefined);
  }, [currentCountry, countrySource, hintSource, router]);

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 pl-5 text-small">
      <button type="button" onClick={locate.run} disabled={locate.busy} className="inline-flex min-h-11 items-center gap-2 font-bold text-[#0B5D66] disabled:opacity-60">
        <Locate color="#0B5D66" />
        {locate.busy ? t("address.locating") : t("address.use_my_location")}
      </button>
      {problem && <span role="status" className="text-muted">{problem}</span>}
    </div>
  );
}
