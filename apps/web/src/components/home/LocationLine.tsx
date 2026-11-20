// Where the visitor is (R6, R8; one action since the domain round): one line above the home content,
// not in the header. From getContext's `location` (resolveLocation in @bhojango/i18n).
// - A known live city (their delivery address's, the city they picked, or the IP's guess when it is
//   inside a live zone): "<City>, <CC> · Change". "Change" opens the city list (/cities?choose=1).
// - Anything else (nothing known, an IP guess outside every live zone, an address we don't serve):
//   only "Set your delivery location", which opens the address box. Never a guessed town, never the
//   country's first live city.
import Link from "next/link";

import { Pin } from "@/components/Icons";
import { getContext } from "@/lib/prefs";
import { SetLocation } from "./SetLocation";

export async function LocationLine() {
  const { t, location, country } = await getContext();
  const { place, code, served, source } = location;
  const known = served && place && code ? { label: t("location.place", { city: place, country: code }), path: location.city?.path } : null;
  return (
    <nav aria-label={t("location.label")}>
      <p
        data-testid="location-line"
        data-source={source}
        data-served={served ? "1" : "0"}
        className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-body text-muted"
      >
        <Pin size={16} color="#0B5D66" className="shrink-0" />
        {known ? (
          <>
            <b data-testid="location-place" className="font-semibold text-[#111418]">
              {known.path ? (
                <Link href={known.path} className="text-[#111418] underline-offset-4 hover:text-[#111418] hover:underline">
                  {known.label}
                </Link>
              ) : (
                known.label
              )}
            </b>
            <span aria-hidden="true">{" · "}</span>
            <Link href="/cities?choose=1" data-testid="change-city" aria-label={t("location.change_city")}
              className="font-semibold text-[#0B5D66] underline-offset-4 hover:underline">
              {t("location.change")}
            </Link>
          </>
        ) : (
          <SetLocation label={t("location.set")} country={country?.code ?? null} />
        )}
      </p>
    </nav>
  );
}
