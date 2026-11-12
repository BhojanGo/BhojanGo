import * as React from "react";

/** Logo C: the steaming "b" (docs/design/logo). "teal" on light grounds, "white" on Peacock. */
export function LogoMark({ size = 40, tone = "teal", title = "BhojanGo" }: { size?: number; tone?: "teal" | "white"; title?: string }) {
  const stroke = tone === "white" ? "#FFFFFF" : "#0B5D66";
  const steam = tone === "white" ? "#E8A93C" : "#D4932A";
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label={title}>
      <path d="M11 5.5v24" stroke={stroke} strokeWidth="5" strokeLinecap="round" fill="none" />
      <circle cx="20.5" cy="25" r="8.5" fill="none" stroke={stroke} strokeWidth="5" />
      <path d="M18.5 13.5c-1.6-1.8 1.6-3.4 0-5.6M24.5 13.5c-1.6-1.8 1.6-3.4 0-5.6" stroke={steam} strokeWidth="2.2" strokeLinecap="round" fill="none" />
    </svg>
  );
}

/** The mark and the lowercase wordmark, with an optional quiet suffix ("admin"). */
export function Logo({ size = 32, suffix }: { size?: number; suffix?: string }) {
  return (
    <span className="inline-flex items-center gap-2.5 font-display text-xl font-bold tracking-[-0.4px] text-kohl">
      <LogoMark size={size} />
      bhojango
      {suffix && <span className="font-sans text-sm font-semibold tracking-normal text-muted">{suffix}</span>}
    </span>
  );
}
