// Error reports to Sentry (R19, the free plan), in the browser. Off unless the build sets
// NEXT_PUBLIC_SENTRY_DSN: then no init, no network, and the SDK's chunk is never loaded.
const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (DSN) {
  void import("@sentry/nextjs").then((Sentry) =>
    Sentry.init({ dsn: DSN, environment: process.env.NEXT_PUBLIC_APP_ENV || "development", tracesSampleRate: 0 }),
  );
}
