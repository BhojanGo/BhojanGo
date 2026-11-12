// The web app calls the services directly (no gateway): core_api for browsing,
// ordering and paying, realtime for live tracking. Server-rendered pages (city
// and restaurant pages) read core_api from inside the network when
// CORE_API_INTERNAL_URL is set (Docker), else the public URL.

/** @type {import('next').NextConfig} */
const nextConfig = {
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
