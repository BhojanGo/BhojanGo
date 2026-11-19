// R19: the EAS project id push tokens are issued for. Pure (test/push.test.ts).
// config/store.json holds named placeholders until the real ids exist; a build with a
// placeholder simply doesn't register for push (no error, no prompt).

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** The EAS project id when it is a real one (a UUID), else null (placeholder, missing). */
export function easProjectId(value: unknown): string | null {
  return typeof value === "string" && UUID.test(value.trim()) ? value.trim() : null;
}

/** What the API calls this phone's platform. */
export function pushPlatform(os: string): "ios" | "android" | null {
  return os === "ios" ? "ios" : os === "android" ? "android" : null;
}
