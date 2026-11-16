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

/**
 * The lockup as drawn on BrandLogo.html (route C): the mark, then "bhojango" in
 * Inter 700, kohl, spaced from the mark (12 px gap at a 52 px mark).
 * The wordmark is the h3 token (17 px on a phone, fluid to 20 px): only sizes
 * from the type scale. Optional quiet suffix ("admin").
 */
export function Logo({ size = 32, suffix, tone = "teal" }: { size?: number; suffix?: string; tone?: "teal" | "white" }) {
  return (
    <span className="inline-flex items-center" style={{ gap: Math.round(size * (12 / 52)) }}>
      <LogoMark size={size} tone={tone} />
      <span data-testid="logo-wordmark" className={`text-h3 font-bold leading-none tracking-[-0.6px] ${tone === "white" ? "text-white" : "text-kohl"}`}>bhojango</span>
      {suffix && <span className="text-label tracking-normal text-muted" style={{ marginLeft: Math.round(size * 0.15) }}>{suffix}</span>}
    </span>
  );
}
