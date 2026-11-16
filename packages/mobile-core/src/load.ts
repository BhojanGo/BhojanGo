// R9: what a screen does when the API can't be reached. Every GET the apps make
// gives up after FIRST_LOAD_TIMEOUT_MS (a server that doesn't answer must not leave
// a screen loading forever); the screen then shows <LoadError> (ui/load-error.tsx)
// with a Retry button that runs its load again.
// Pure: no React Native imports (test/load.test.ts runs it under node --test).

/** A GET that hasn't answered by then fails, so the error shows by ~8 s (never more than 10). */
export const FIRST_LOAD_TIMEOUT_MS = 8000;

/** The request was given up: the server didn't answer in time. */
export class RequestTimeoutError extends Error {
  constructor(ms: number) {
    super(`No answer in ${Math.round(ms / 1000)} s`);
    this.name = "RequestTimeoutError";
  }
}

type Fetch = (input: Request) => Promise<Response>;

/**
 * A fetch for openapi-fetch (createApi's `fetch`) that gives up a GET or HEAD after
 * `ms`. Other methods (placing an order, paying, uploading) are left to finish: giving
 * them up could leave a person unsure whether it went through; `everyMethod` is for a POST
 * that only reads (the bag's price quote), passed per request.
 * `base` is read on every call (tests replace it; React Native's is globalThis.fetch).
 */
export function timeoutFetch(ms: number = FIRST_LOAD_TIMEOUT_MS, base: () => Fetch = () => globalThis.fetch, everyMethod = false): Fetch {
  return (request: Request) => {
    const fetchImpl = base();
    if (!everyMethod && request.method !== "GET" && request.method !== "HEAD") return fetchImpl(request);
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const outer = request.signal;
    const onAbort = () => controller?.abort();
    outer?.addEventListener?.("abort", onAbort);
    let timer: ReturnType<typeof setTimeout> | undefined;
    // The race fails the request on time even where a fetch ignores its signal.
    const late = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        controller?.abort();
        reject(new RequestTimeoutError(ms));
      }, ms);
    });
    const sent = controller ? new Request(request, { signal: controller.signal }) : request;
    return Promise.race([fetchImpl(sent), late]).finally(() => {
      clearTimeout(timer);
      outer?.removeEventListener?.("abort", onAbort);
    });
  };
}

/**
 * Why a load failed, for the words on the error state:
 *   offline  no connection at all (the phone has no internet, or nothing answers at our address)
 *   timeout  our servers didn't answer in time
 *   server   our servers answered with an error (5xx)
 *   refused  the API said no (4xx): its message says why
 */
export type LoadFailure = "offline" | "timeout" | "server" | "refused";

export function loadFailure(error: unknown): LoadFailure {
  if (error instanceof RequestTimeoutError || (error as { name?: string } | null)?.name === "RequestTimeoutError") return "timeout";
  const status = (error as { status?: unknown } | null)?.status;
  if (typeof status === "number") return status >= 500 || status === 0 ? "server" : status === 408 ? "timeout" : "refused";
  // fetch rejects with a TypeError ("Network request failed") when there is no connection.
  return "offline";
}

/** What a first load is doing. */
export interface LoadState<T> {
  status: "loading" | "ready" | "error";
  data: T | null;
  error: unknown;
}

/**
 * A screen's first load with Retry: run() starts (or re-runs) it; onChange hears every
 * state. A slower, older run never overwrites a newer one. useFirstLoad (ui/load-error.tsx)
 * is the React side.
 */
export function createFirstLoad<T>(load: () => Promise<T>, onChange: (state: LoadState<T>) => void) {
  let run = 0;
  let disposed = false;
  let state: LoadState<T> = { status: "loading", data: null, error: null };
  const emit = (next: LoadState<T>) => {
    state = next;
    if (!disposed) onChange(next);
  };
  return {
    get state() {
      return state;
    },
    /** Load (again). Keeps the data already shown while it reloads. */
    async run(): Promise<void> {
      const mine = ++run;
      emit({ status: "loading", data: state.data, error: null });
      try {
        const data = await load();
        if (mine === run) emit({ status: "ready", data, error: null });
      } catch (error) {
        if (mine === run) emit({ status: "error", data: state.data, error });
      }
    },
    dispose() {
      disposed = true;
    },
  };
}
