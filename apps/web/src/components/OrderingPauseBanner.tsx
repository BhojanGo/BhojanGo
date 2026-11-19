"use client";
// R17: "Ordering in <city> is paused for now…" while an admin has paused ordering (incident tools).
// The layout fetches the active pauses (public, no admin reasons); this strip shows the ones for the
// page's country and city (/<country>/<city>/…), and all of them on pages that aren't about a place
// (home, checkout, account). Text in the visitor's language; the admin's note as written.
import { usePathname } from "next/navigation";

import { useT } from "@/lib/i18n";
import { type OrderingPause, shownPauses } from "@/lib/pauses";

export type { OrderingPause };

export function OrderingPauseBanner({ pauses }: { pauses: OrderingPause[] }) {
  const t = useT();
  const shown = shownPauses(pauses, usePathname() ?? "/");
  if (!shown.length) return null;
  return (
    <section aria-label={t("incident.paused_everywhere")}>
      {shown.map((p) => (
        <div key={p.id} role="status" data-testid="ordering-paused"
          className="border-b border-[#B3261E] bg-[#F1E3E1] px-4 py-2 text-center text-label text-[#8C1D18] print:hidden">
          {p.scope === "*" ? t("incident.paused_everywhere") : t("incident.paused_area", { area: p.area })}
          {p.note ? <> {p.note}</> : null}
        </div>
      ))}
    </section>
  );
}
