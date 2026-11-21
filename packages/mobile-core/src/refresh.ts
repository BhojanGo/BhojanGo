// R27: the session refresh can never hang. R26's kitchen tablet stopped updating after ~75 min with
// no error: the access token (15 min) expired, a refresh POST hung (React Native's Android fetch has
// no read timeout), and every later request waited on that one shared, never-settling refresh.
// Here a refresh gives up after REFRESH_TIMEOUT_MS (its request is aborted too) and the shared promise
// is always cleared once it settles, so the next request starts a fresh refresh.
// Pure: no React Native imports (test/refresh.test.ts runs it under node --test).

/** A refresh that hasn't answered by then fails (a dead connection, not a refused session). */
export const REFRESH_TIMEOUT_MS = 15000;

/** The refresh didn't answer in time. Not a sign-out: the next request tries again. */
export class RefreshTimeoutError extends Error {
  constructor(ms: number) {
    super(`The session refresh got no answer in ${Math.round(ms / 1000)} s`);
    this.name = "RefreshTimeoutError";
  }
}

/**
 * One run at a time, shared by every caller while it runs, and never longer than `ms`: the run
 * gets an AbortSignal that fires at the deadline, and its promise rejects with RefreshTimeoutError
 * then even if the run ignores the signal. Settled (answered, failed or timed out): the next call
 * starts a new run.
 */
export function singleFlight<T>(run: (signal: AbortSignal | null) => Promise<T>, ms: number = REFRESH_TIMEOUT_MS): () => Promise<T> {
  let current: Promise<T> | null = null;
  return () => {
    if (current) return current;
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const late = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        controller?.abort();
        reject(new RefreshTimeoutError(ms));
      }, ms);
    });
    // Started inside a promise chain, so even a run that throws at once settles asynchronously
    // and `current` is cleared after it was set.
    const started = Promise.resolve().then(() => run(controller?.signal ?? null));
    const settled: Promise<T> = Promise.race([started, late]).finally(() => {
      clearTimeout(timer);
      if (current === settled) current = null;
    });
    current = settled;
    return settled;
  };
}
