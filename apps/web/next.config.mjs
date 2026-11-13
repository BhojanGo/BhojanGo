// The web app calls the services directly (no gateway): core_api for browsing,
// ordering and paying, realtime for live tracking. Server-rendered pages (city
// and restaurant pages) read core_api from inside the network when
// CORE_API_INTERNAL_URL is set (Docker), else the public URL.

import { securityHeaders } from "@bhojango/ui/security-headers";

const CORE = process.env.NEXT_PUBLIC_CORE_URL ?? "http://localhost:8001";
const REALTIME = process.env.NEXT_PUBLIC_REALTIME_URL ?? "http://localhost:8004";

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/:path*",
      headers: securityHeaders({
        connect: [CORE, REALTIME],
        // kitchen photos (S3/CloudFront; LocalStack in make dev)
        img: ["https:", ...(process.env.NODE_ENV === "production" ? [] : ["http://localhost:4566"])],
        // the payment providers' checkout (Razorpay in India, Stripe in the US)
        script: ["https://checkout.razorpay.com", "https://js.stripe.com"],
        frame: ["https://api.razorpay.com", "https://checkout.razorpay.com", "https://js.stripe.com", "https://hooks.stripe.com"],
        geolocation: true,
      }),
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
      { source: "/login", destination: "/sign-in", permanent: true },
      { source: "/signup", destination: "/sign-in", permanent: true },
      { source: "/cart", destination: "/checkout", permanent: true },
    ];
  },
};

export default nextConfig;
