// The web app calls the services directly (no gateway): core_api for browsing,
// ordering and paying, realtime for live tracking. Server-rendered pages (city
// and restaurant pages) read core_api from inside the network when
// CORE_API_INTERNAL_URL is set (Docker), else the public URL.

import { securityHeaders } from "@bhojango/ui/security-headers";

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
      // The Content-Security-Policy comes from src/proxy.ts, with a fresh nonce for each page (R22 S9).
      headers: [...noindex, ...securityHeaders({
        // Apple Pay / Google Pay run in Stripe's frames: they need the Payment Request API (Permissions-Policy)
        payment: ["https://js.stripe.com"],
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
