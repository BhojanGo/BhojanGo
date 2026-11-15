"use client";
// "Looks like you're near …" under the landing page's address box: from the
// visitor's IP (asked from the browser, so it's their address, not the server's),
// a hint only, shown only when that place is inside an open zone. The IP's
// country is also remembered (cookie) for the header's country and languages.

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
  city_code: string | null;
  city_name: string | null;
  city_path: string | null;
  served: boolean;
}

export function HintRow({ currentCountry, countrySource }: { currentCountry: string | null; countrySource: string }) {
  const t = useT();
  const router = useRouter();
  const [hint, setHint] = useState<Hint | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const locate = useMyLocation(setProblem);

  useEffect(() => {
    let cached: Hint | null = null;
    try {
      cached = JSON.parse(sessionStorage.getItem("bg_hint") ?? "null");
    } catch {
      /* private mode */
    }
    const apply = (h: Hint) => {
      setHint(h);
      // The IP's country beats the browser locale, but never an address or a choice.
      if (h.country && h.country !== currentCountry && (countrySource === "locale" || countrySource === "none")) {
        setCookie("bg_hint", h.country);
        router.refresh();
      }
    };
    if (cached) return apply(cached);
    fetch(`${urls.core}/api/v1/markets/hint`)
      .then((r) => (r.ok ? r.json() : null))
      .then((h: Hint | null) => {
        if (!h) return;
        try {
          sessionStorage.setItem("bg_hint", JSON.stringify(h));
        } catch {
          /* private mode */
        }
        apply(h);
      })
      .catch(() => undefined);
  }, [currentCountry, countrySource, router]);

  const near = hint?.served && hint.place ? [hint.place, hint.region].filter(Boolean).join(", ") : null;
  return (
    <div className="mt-4 flex max-w-[694px] flex-wrap items-center gap-x-3 gap-y-1 rounded-[14px] border border-[#E2E7E8] bg-white px-4 py-3 text-sm">
      <Locate color="#0B5D66" />
      {near ? (
        <span className="flex-grow">
          <button
            type="button"
            className="font-bold text-[#111418]"
            onClick={() => hint?.city_path && router.push(hint.city_path)}
          >
            {t("address.near_hint", { place: near })}
          </button>{" "}
          <span className="text-[#4C5A5E]">{t("address.we_deliver_there")}</span>
        </span>
      ) : (
        <span className="flex-grow text-[#4C5A5E]">{problem ?? ""}</span>
      )}
      <button type="button" onClick={locate.run} disabled={locate.busy} className="font-extrabold text-[#0B5D66] disabled:opacity-60">
        {locate.busy ? t("address.locating") : t("address.use_my_location")}
      </button>
      {problem && near && <span role="status" className="basis-full text-[#4C5A5E]">{problem}</span>}
    </div>
  );
}
