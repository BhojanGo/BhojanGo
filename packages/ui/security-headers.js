// Security headers for the web and admin apps (security pass: OWASP ZAP flagged
// a missing CSP and anti-clickjacking header, Medium; and missing hardening
// headers, Low).
//
// R22 security review (S9): the Content-Security-Policy is no longer a fixed
// header with script-src 'unsafe-inline'. Each app's proxy (src/proxy.ts, Next
// middleware) makes a fresh nonce for every page and sends
// contentSecurityPolicy(options, nonce); Next puts that nonce on its own inline
// and bundle scripts, and 'strict-dynamic' lets those scripts load the rest
// (Stripe.js, Razorpay's checkout, Google sign-in). An injected inline script
// has no nonce, so the browser refuses it. JSON-LD (<script type="application/ld+json">)
// is data, never run, and S1's escaping keeps it from closing its tag.
// securityHeaders(options) is everything else, set from each app's next.config.

/**
 * @typedef {{ connect?: string[], img?: string[], script?: string[], style?: string[], frame?: string[], worker?: string[],
 *   geolocation?: boolean, popups?: boolean, payment?: string[] }} HeaderOptions
 * `payment` lets these origins' frames use the Payment Request API (Stripe's Apple Pay / Google Pay frames).
 * `worker` adds a worker-src (e.g. "blob:" for a WebGL map); `popups` relaxes the opener policy to
 * same-origin-allow-popups (a sign-in provider's popup must message back to the page).
 */

/**
 * The page's Content-Security-Policy. With a nonce (pages, from the proxy): only scripts that carry
 * it run, plus what they load ('strict-dynamic'); the host list is the fallback for browsers
 * without 'strict-dynamic'. Without one (files the proxy doesn't see): scripts from our origin only.
 * Never 'unsafe-inline' for scripts. Development adds 'unsafe-eval' (React's dev tools need it).
 * @param {HeaderOptions} o
 * @param {string} [nonce]
 */
function contentSecurityPolicy(o = {}, nonce) {
  const dev = process.env.NODE_ENV !== "production";
  const ws = (o.connect ?? []).filter((u) => u.startsWith("http")).map((u) => u.replace(/^http/, "ws"));
  const scripts = ["'self'", ...(nonce ? [`'nonce-${nonce}'`, "'strict-dynamic'"] : []), ...(dev ? ["'unsafe-eval'"] : []), ...(o.script ?? [])];
  return [
    "default-src 'self'",
    `script-src ${scripts.join(" ")}`,
    `style-src 'self' 'unsafe-inline' ${(o.style ?? []).join(" ")}`.trim(),
    `img-src 'self' data: blob: ${(o.img ?? []).join(" ")}`.trim(),
    "font-src 'self' data:",
    `connect-src 'self' ${[...(o.connect ?? []), ...ws].join(" ")}`.trim(),
    ...((o.worker ?? []).length ? [`worker-src 'self' ${o.worker.join(" ")}`] : []),
    `frame-src ${(o.frame ?? []).length ? o.frame.join(" ") : "'none'"}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}

/** A nonce for one response: 16 random bytes, base64. */
function newNonce() {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

/**
 * Every header but the CSP (the proxy sets that one, with the page's nonce), for next.config.
 * @param {HeaderOptions} o
 */
function securityHeaders(o = {}) {
  return [
    { key: "X-Frame-Options", value: "DENY" },
    // HTTPS only (ignored by browsers over plain HTTP, so localhost is unaffected).
    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: `camera=(), microphone=(), payment=(self${(o.payment ?? []).map((u) => ` "${u}"`).join("")}), geolocation=(${o.geolocation ? "self" : ""})` },
    { key: "Cross-Origin-Opener-Policy", value: o.popups ? "same-origin-allow-popups" : "same-origin" },
    { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
  ];
}

module.exports = { contentSecurityPolicy, newNonce, securityHeaders };
