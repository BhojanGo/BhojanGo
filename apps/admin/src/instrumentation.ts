// Error reports to Sentry (R19, the free plan), server side. Off unless SENTRY_DSN (or the
// browser's NEXT_PUBLIC_SENTRY_DSN) is set: then no init, no network, and the SDK isn't loaded.
const DSN = process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN || "";

export async function register(): Promise<void> {
  if (!DSN) return;
  const Sentry = await import("@sentry/nextjs");
  Sentry.init({ dsn: DSN, environment: process.env.APP_ENV || "development", tracesSampleRate: 0 });
}

export async function onRequestError(...args: Parameters<typeof import("@sentry/nextjs").captureRequestError>): Promise<void> {
  if (!DSN) return;
  const Sentry = await import("@sentry/nextjs");
  Sentry.captureRequestError(...args);
}
