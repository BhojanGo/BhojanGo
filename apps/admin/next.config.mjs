// identity, catalog, orders and payments all run in core_api (:8001) since P1;
// the per-area env vars are kept so deployments can still point them anywhere.
/**
 * Resolve a backend service URL. In production a missing env var is a hard error
 * (fail loud) rather than a silent fallback to localhost that breaks every request.
 */
function svc(envVar, devFallback) {
  const url = process.env[envVar];
  if (url) return url;
  if (process.env.NODE_ENV === "production") {
    throw new Error(`${envVar} must be set in production`);
  }
  return devFallback;
}

import { securityHeaders } from "@bhojango/ui/security-headers";

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  // The environment for the browser bundle too (Sentry's environment tag).
  env: { NEXT_PUBLIC_APP_ENV: process.env.APP_ENV ?? "" },
  async headers() {
    // The admin console is never for search engines, in any environment (header as well as meta).
    // The Content-Security-Policy comes from src/proxy.ts, with a fresh nonce for each page (R22 S9).
    const noindex = { key: "X-Robots-Tag", value: "noindex, nofollow" };
    return [{ source: "/:path*", headers: [noindex, ...securityHeaders()] }];
  },
  async rewrites() {
    return [
      {
        source: "/api/user/:path*",
        destination: `${svc("USER_SVC_URL", "http://localhost:8001")}/api/v1/:path*`,
      },
      {
        source: "/api/restaurant/:path*",
        destination: `${svc("RESTAURANT_SVC_URL", "http://localhost:8001")}/api/v1/:path*`,
      },
      {
        source: "/api/order/:path*",
        destination: `${svc("ORDER_SVC_URL", "http://localhost:8001")}/api/v1/:path*`,
      },
      {
        // realtime: the dispatch map's riders and SOS alerts (P21)
        source: "/api/realtime/:path*",
        destination: `${svc("REALTIME_SVC_URL", "http://localhost:8004")}/api/v1/:path*`,
      },
      {
        source: "/api/payment/:path*",
        destination: `${svc("PAYMENT_SVC_URL", "http://localhost:8001")}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
