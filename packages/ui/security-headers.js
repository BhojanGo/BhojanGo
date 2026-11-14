// Security headers for the web and admin apps (security pass: OWASP ZAP flagged
// a missing CSP and anti-clickjacking header, Medium; and missing hardening
// headers, Low). Used from each app's next.config.
//
// script-src keeps 'unsafe-inline': Next's bootstrap and our JSON-LD are inline
// scripts. Everything else is locked to what the app actually loads.

/** @param {{ connect?: string[], img?: string[], script?: string[], frame?: string[], geolocation?: boolean }} o */
function securityHeaders(o = {}) {
  const dev = process.env.NODE_ENV !== "production";
  const ws = (o.connect ?? []).filter((u) => u.startsWith("http")).map((u) => u.replace(/^http/, "ws"));
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""} ${(o.script ?? []).join(" ")}`.trim(),
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: ${(o.img ?? []).join(" ")}`.trim(),
    "font-src 'self' data:",
    `connect-src 'self' ${[...(o.connect ?? []), ...ws].join(" ")}`.trim(),
    `frame-src ${(o.frame ?? []).length ? o.frame.join(" ") : "'none'"}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
  return [
    { key: "Content-Security-Policy", value: csp },
    { key: "X-Frame-Options", value: "DENY" },
    // HTTPS only (ignored by browsers over plain HTTP, so localhost is unaffected).
    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: `camera=(), microphone=(), payment=(self), geolocation=(${o.geolocation ? "self" : ""})` },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
  ];
}

module.exports = { securityHeaders };
