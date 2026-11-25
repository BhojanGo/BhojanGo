/**
 * R43: the website's server-side calls to core_api. Each gives up after SSR_TIMEOUT_MS, and once one has failed
 * (core_api stopped, unreachable or too slow) the next calls in the following CORE_DOWN_MS fail at once, so a page
 * that needs several answers shows its "couldn't load" state in well under 4 s instead of waiting on each in turn.
 */
export const SSR_TIMEOUT_MS = 2500;
export const CORE_DOWN_MS = 5000;

let downUntil = 0;

export async function coreFetch(url: string, init: RequestInit & { next?: { revalidate?: number | false; tags?: string[] } } = {}): Promise<Response> {
  if (Date.now() < downUntil) throw new Error("core_api unreachable (it failed a moment ago)");
  try {
    return await fetch(url, { ...init, signal: AbortSignal.timeout(SSR_TIMEOUT_MS) });
  } catch (e) {
    downUntil = Date.now() + CORE_DOWN_MS;
    throw e;
  }
}
