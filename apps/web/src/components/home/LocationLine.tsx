// Where the visitor is (R6): one line above the home content, not in the header:
// "<city>, <CC> · Change city". The city and the 2-letter country code come from
// Markets (getContext: the address's city, else the chosen city, else the IP
// hint's, else the country's first live city). "Change city" opens the city list
// (/cities?choose=1); a city in another country switches currency and languages.
import Link from "next/link";

import { Pin } from "@/components/Icons";
import { getContext } from "@/lib/prefs";

export async function LocationLine() {
  const { t, city, country } = await getContext();
  if (!country) return null;
  return (
    <nav aria-label={t("location.label")}>
      <p data-testid="location-line" className="m-0 text-body text-[#4C5A5E]">
        <Pin size={16} color="#0B5D66" className="mr-2 inline-block align-[-2px]" />
        {city && (
          <>
            <b className="font-semibold text-[#111418]">{t("location.place", { city: city.name, country: country.code })}</b>
            {" · "}
          </>
        )}
        <Link href="/cities?choose=1" className="font-semibold text-[#0B5D66] underline-offset-4 hover:underline">
          {t("location.change_city")}
        </Link>
      </p>
    </nav>
  );
}
