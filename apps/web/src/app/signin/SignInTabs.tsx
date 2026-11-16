"use client";
// /signin (round 8, D5): "Phone" and "Email" as two equal tabs (same size and weight;
// arrow keys move between them, per the WAI-ARIA tabs pattern), Google below both.
import { useRef, useState, type ReactNode } from "react";

import { useT } from "@/lib/i18n";

export type Way = "phone" | "email";
const WAYS: Way[] = ["phone", "email"];

export function SignInTabs({ initial, phone, email, after }: { initial: Way; phone: ReactNode; email: ReactNode; after?: ReactNode }) {
  const t = useT();
  const [way, setWay] = useState<Way>(initial);
  const tabs = useRef<Record<Way, HTMLButtonElement | null>>({ phone: null, email: null });

  function choose(next: Way, focus = false) {
    setWay(next);
    if (focus) tabs.current[next]?.focus();
    // Keep the choice in the address (a link or a reload opens the same tab).
    const url = new URL(window.location.href);
    url.searchParams.set("way", next);
    window.history.replaceState(window.history.state, "", url);
  }

  return (
    <div>
      <h1 className="m-0 text-h1 leading-[1.1] tracking-[-0.8px] md:tracking-[-1px]">{t("signin.heading")}</h1>
      <p className="m-0 mt-2 hidden text-body text-[#3D4A4E] md:block">{t("signin.sub")}</p>
      <div role="tablist" aria-label={t("auth.ways_label")} className="mt-6 grid grid-cols-2 gap-1 rounded-full bg-[#EEF1F1] p-1 md:mt-8">
        {WAYS.map((w) => {
          const on = w === way;
          return (
            <button
              key={w}
              ref={(el) => {
                tabs.current[w] = el;
              }}
              id={`tab-${w}`}
              type="button"
              role="tab"
              aria-selected={on}
              aria-controls={`panel-${w}`}
              tabIndex={on ? 0 : -1}
              onClick={() => choose(w)}
              onKeyDown={(e) => {
                const i = WAYS.indexOf(w);
                if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                  e.preventDefault();
                  choose(WAYS[(i + (e.key === "ArrowRight" ? 1 : WAYS.length - 1)) % WAYS.length] as Way, true);
                }
              }}
              className={`h-11 rounded-full text-label font-bold transition-colors ${on ? "bg-white text-[#111418] shadow-[0_1px_3px_rgba(17,20,24,0.16)]" : "text-[#3D4A4E] hover:text-[#111418]"}`}
            >
              {t(w === "phone" ? "auth.tab_phone" : "auth.tab_email")}
            </button>
          );
        })}
      </div>
      {WAYS.map((w) => (
        <div key={w} id={`panel-${w}`} role="tabpanel" aria-labelledby={`tab-${w}`} hidden={w !== way}>
          {w === way && (w === "phone" ? phone : email)}
        </div>
      ))}
      {after}
    </div>
  );
}
