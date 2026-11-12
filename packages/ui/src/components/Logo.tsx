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
 * Familjen Grotesk 700, kohl, sized and spaced from the mark (52 px mark :
 * 34 px wordmark, -1 px tracking, 12 px gap). Optional quiet suffix ("admin").
 */
export function Logo({ size = 32, suffix, tone = "teal" }: { size?: number; suffix?: string; tone?: "teal" | "white" }) {
  const text = Math.round(size * (34 / 52) * 10) / 10;
  return (
    <span className="inline-flex items-center" style={{ gap: Math.round(size * (12 / 52)) }}>
      <LogoMark size={size} tone={tone} />
      <span style={{ fontFamily: "var(--font-display), 'Familjen Grotesk', system-ui, sans-serif", fontWeight: 700, fontSize: text,
        letterSpacing: `${-(text / 34)}px`, lineHeight: 1, color: tone === "white" ? "#FFFFFF" : "#111418" }}>bhojango</span>
      {suffix && <span className="font-sans text-sm font-semibold tracking-normal text-muted" style={{ marginLeft: Math.round(size * 0.15) }}>{suffix}</span>}
    </span>
  );
}
