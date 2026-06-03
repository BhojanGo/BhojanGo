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

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/user/:path*",
        destination: `${svc("USER_SVC_URL", "http://localhost:8001")}/api/v1/:path*`,
      },
      {
        source: "/api/restaurant/:path*",
        destination: `${svc("RESTAURANT_SVC_URL", "http://localhost:8002")}/api/v1/:path*`,
      },
      {
        source: "/api/order/:path*",
        destination: `${svc("ORDER_SVC_URL", "http://localhost:8003")}/api/v1/:path*`,
      },
      {
        source: "/api/payment/:path*",
        destination: `${svc("PAYMENT_SVC_URL", "http://localhost:8005")}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
