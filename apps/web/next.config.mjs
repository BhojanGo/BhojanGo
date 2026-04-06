import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.amazonaws.com" },
      { protocol: "https", hostname: "**.cloudfront.net" },
      { protocol: "https", hostname: "**.unsplash.com" },
    ],
  },
  async rewrites() {
    return [
      { source: "/api/user/:path*", destination: `${process.env.USER_SVC_URL ?? "http://localhost:8001"}/api/v1/:path*` },
      { source: "/api/restaurant/:path*", destination: `${process.env.RESTAURANT_SVC_URL ?? "http://localhost:8002"}/api/v1/:path*` },
      { source: "/api/order/:path*", destination: `${process.env.ORDER_SVC_URL ?? "http://localhost:8003"}/api/v1/:path*` },
      { source: "/api/payment/:path*", destination: `${process.env.PAYMENT_SVC_URL ?? "http://localhost:8005"}/api/v1/:path*` },
    ];
  },
};

export default withNextIntl(nextConfig);
