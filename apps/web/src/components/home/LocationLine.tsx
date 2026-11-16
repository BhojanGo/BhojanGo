// Where the visitor is (R6, R8): one line above the home content, not in the header.
// From getContext's `location` (resolveLocation in @bhojango/i18n): the delivery
// address's city, else the city they picked, else the IP's own town shown as itself
// ("Meridian, ID", with "We deliver here" only inside an open zone), else nothing.
// Where we don't serve (or know nothing), "Set your delivery location" opens the
// address box. Never the country's first live city. "Change city" opens the city
// list (/cities?choose=1); a city in another country switches currency and languages.
import Link from "next/link";

import { Pin } from "@/components/Icons";
import { getContext } from "@/lib/prefs";
import { SetLocation } from "./SetLocation";

export async function LocationLine() {
  const { t, location, country } = await getContext();
  const { place, code, served, deliversHere, source } = location;
  const label = place && code ? t("location.place", { city: place, country: code }) : null;
  return (
    <nav aria-label={t("location.label")}>
      <p
        data-testid="location-line"
        data-source={source}
        data-served={served ? "1" : "0"}
        className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-body text-muted"
      >
        <Pin size={16} color="#0B5D66" className="shrink-0" />
        {label && (
          <b data-testid="location-place" className="font-semibold text-[#111418]">
            {location.city && served ? (
              <Link href={location.city.path} className="text-[#111418] underline-offset-4 hover:text-[#111418] hover:underline">
                {label}
              </Link>
            ) : (
              label
            )}
          </b>
        )}
        {deliversHere && (
          <>
            <span aria-hidden="true">{" · "}</span>
            <span data-testid="delivers-here" className="text-[#0B5D66]">{t("location.delivers_here")}</span>
          </>
        )}
        {!served && (
          <>
            {label && <span aria-hidden="true">{" · "}</span>}
            <SetLocation label={t("location.set")} country={country?.code ?? null} />
          </>
        )}
        <span aria-hidden="true">{" · "}</span>
        <Link href="/cities?choose=1" data-testid="change-city" className="font-semibold text-[#0B5D66] underline-offset-4 hover:underline">
          {t("location.change_city")}
        </Link>
      </p>
    </nav>
  );
}
