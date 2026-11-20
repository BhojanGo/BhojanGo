// What the website's pages may load (R22 S9): the Content-Security-Policy that src/proxy.ts
// sends with each page's own nonce (packages/ui/security-headers.js contentSecurityPolicy).
import type { HeaderOptions } from "@bhojango/ui/security-headers";

const CORE = process.env.NEXT_PUBLIC_CORE_URL ?? "http://localhost:8001";
const REALTIME = process.env.NEXT_PUBLIC_REALTIME_URL ?? "http://localhost:8004";
const MAP_TILES = "https://tiles.openfreemap.org";
// Sentry (R19): the browser sends error reports to the DSN's host, only when a DSN is set.
const SENTRY = (() => {
  try {
    return process.env.NEXT_PUBLIC_SENTRY_DSN ? [new URL(process.env.NEXT_PUBLIC_SENTRY_DSN).origin] : [];
  } catch {
    return [];
  }
})();

export const WEB_CSP: HeaderOptions = {
  // core_api and realtime; the tracking map's tiles, fonts and sprites (OpenFreeMap, free, no key);
  // Google sign-in (Google Identity Services); Stripe.js (Payment Element, 3-D Secure)
  connect: [CORE, REALTIME, MAP_TILES, "https://accounts.google.com/gsi/", "https://api.stripe.com", ...SENTRY],
  // kitchen photos (S3/CloudFront; LocalStack in make dev); map tiles
  img: ["https:", MAP_TILES, ...(process.env.NODE_ENV === "production" ? [] : ["http://localhost:4566"])],
  // the payment providers' checkout (Razorpay in India, Stripe in the US); Google sign-in. With a
  // nonce and 'strict-dynamic' these load because our own (nonced) scripts add them.
  script: ["https://checkout.razorpay.com", "https://js.stripe.com", "https://accounts.google.com/gsi/client"],
  style: ["https://accounts.google.com/gsi/style"],
  frame: ["https://api.razorpay.com", "https://checkout.razorpay.com", "https://js.stripe.com", "https://hooks.stripe.com", "https://accounts.google.com/gsi/"],
  // MapLibre GL runs its tile parsing in a worker (a blob: URL when the script is on another origin)
  worker: ["blob:"],
};
