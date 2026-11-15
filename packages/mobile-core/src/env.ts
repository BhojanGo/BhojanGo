// Which environment an app build talks to (round 4): "production", "qa" or
// "local". Set by EXPO_PUBLIC_APP_ENV, which tools/mobile/env-profile.sh writes
// into apps/<app>/.env.local (qa | local) and a store build sets to production.
// Every environment but production is a test site and shows the test banner.
// Pure: no React Native imports (test/env.test.ts).

export type AppEnv = "production" | "qa" | "local" | (string & {});

/**
 * The environment from the build's variables: EXPO_PUBLIC_APP_ENV, else the older
 * EXPO_PUBLIC_ENV, else "local" for a development build and "production" for a
 * release build that says nothing (a store build must never show the banner by accident;
 * the QA and local profiles always set the variable).
 */
export function resolveAppEnv(vars: { appEnv?: string | null; env?: string | null; dev?: boolean }): AppEnv {
  const v = (vars.appEnv || vars.env || "").trim().toLowerCase();
  if (v) return v === "prod" ? "production" : v;
  return vars.dev ? "local" : "production";
}

/** Not production: demo kitchens, no real orders or payments. */
export function isTestEnvironment(env: AppEnv): boolean {
  return env !== "production";
}

/** This build's environment. Expo inlines EXPO_PUBLIC_* only when written out in full, as here. */
export function appEnv(): AppEnv {
  return resolveAppEnv({
    appEnv: process.env.EXPO_PUBLIC_APP_ENV,
    env: process.env.EXPO_PUBLIC_ENV,
    dev: typeof __DEV__ !== "undefined" && __DEV__,
  });
}
