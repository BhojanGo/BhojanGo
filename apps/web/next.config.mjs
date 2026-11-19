// The web app calls the services directly (no gateway): core_api for browsing,
// ordering and paying, realtime for live tracking. Server-rendered pages (city
// and restaurant pages) read core_api from inside the network when
// CORE_API_INTERNAL_URL is set (Docker), else the public URL.

import { securityHeaders } from "@bhojango/ui/security-headers";

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

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  // The environment for the browser bundle too (APP_ENV is a build arg): client code that must
  // fail closed in production reads it (lib/payments.ts: never the fake payment forms).
  env: { NEXT_PUBLIC_APP_ENV: process.env.APP_ENV ?? "" },
  async headers() {
    // Outside production, a header keeps search engines out too (not only robots.txt).
    const noindex = process.env.APP_ENV === "production" ? [] : [{ key: "X-Robots-Tag", value: "noindex, nofollow" }];
    return [{
      source: "/:path*",
      headers: [...noindex, ...securityHeaders({
        // core_api and realtime; the tracking map's tiles, fonts and sprites (OpenFreeMap, free, no key);
        // Google sign-in (Google Identity Services); Stripe.js (Payment Element, 3-D Secure)
        connect: [CORE, REALTIME, MAP_TILES, "https://accounts.google.com/gsi/", "https://api.stripe.com", ...SENTRY],
        // Apple Pay / Google Pay run in Stripe's frames: they need the Payment Request API (Permissions-Policy)
        payment: ["https://js.stripe.com"],
        // kitchen photos (S3/CloudFront; LocalStack in make dev); map tiles
        img: ["https:", MAP_TILES, ...(process.env.NODE_ENV === "production" ? [] : ["http://localhost:4566"])],
        // the payment providers' checkout (Razorpay in India, Stripe in the US); Google sign-in
        script: ["https://checkout.razorpay.com", "https://js.stripe.com", "https://accounts.google.com/gsi/client"],
        style: ["https://accounts.google.com/gsi/style"],
        frame: ["https://api.razorpay.com", "https://checkout.razorpay.com", "https://js.stripe.com", "https://hooks.stripe.com", "https://accounts.google.com/gsi/"],
        // MapLibre GL runs its tile parsing in a worker (a blob: URL when the script is on another origin)
        worker: ["blob:"],
        // Google's sign-in popup must be able to talk back to the page
        popups: true,
        geolocation: true,
      })],
    }];
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.amazonaws.com" },
      { protocol: "https", hostname: "**.cloudfront.net" },
    ],
  },
  async redirects() {
    // Old URLs from before P20.
    return [
      { source: "/restaurants", destination: "/", permanent: true },
      { source: "/login", destination: "/signin", permanent: true },
      { source: "/signup", destination: "/signin", permanent: true },
      { source: "/sign-in", destination: "/signin", permanent: true },
      { source: "/orders", destination: "/account/orders", permanent: true },
      { source: "/cart", destination: "/checkout", permanent: true },
      // Round 8: delivery partners "Deliver with BhojanGo" at /deliver.
      { source: "/ride", destination: "/deliver", permanent: true },
    ];
  },
};

export default nextConfig;
