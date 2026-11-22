// Typed clients for the three services, generated from their OpenAPI documents
// (packages/api-client/openapi, written by backend/tools/dump_openapi.py).
// Regenerate after an API change:
//   cd backend && uv run python tools/dump_openapi.py && pnpm --filter @bhojango/api-client generate
import createClient, { type Client, type Middleware } from "openapi-fetch";

import type { components as CoreComponents, paths as CorePaths } from "./schema/core";
import type { components as RealtimeComponents, paths as RealtimePaths } from "./schema/realtime";
import type { components as WorkerComponents, paths as WorkerPaths } from "./schema/worker";

export type { CorePaths, RealtimePaths, WorkerPaths };
export type CoreSchemas = CoreComponents["schemas"];
export type RealtimeSchemas = RealtimeComponents["schemas"];
export type WorkerSchemas = WorkerComponents["schemas"];

/** Order status names (P11). Apps use these; the older names are gone. */
export type OrderStatus =
  | "pending_payment" | "placed" | "accepted" | "preparing" | "almost_ready" | "ready" | "picked_up" | "delivered" | "cancelled";

export const ACTIVE_STATUSES: OrderStatus[] = ["placed", "accepted", "preparing", "almost_ready", "ready", "picked_up"];

export interface ApiConfig {
  /** e.g. http://localhost:8001 (core_api), :8004 (realtime), :8006 (worker) */
  coreUrl: string;
  realtimeUrl: string;
  workerUrl: string;
  /** The current access token, if signed in. */
  getAccessToken: () => string | null | undefined;
  /** Called once on a 401; return a new access token (after refreshing) or null to give up. */
  refreshAccessToken?: () => Promise<string | null>;
  /**
   * R27: how long a request waits for the shared refresh before it fails (default
   * REFRESH_WAIT_MS). A refresh that never settles must not hold every later request.
   */
  refreshWaitMs?: number;
  /** Called when the session can't be refreshed (sign the person out). */
  onSignedOut?: () => void;
  /** The fetch to send requests with (the apps' gives up a GET that hangs: mobile-core timeoutFetch). */
  fetch?: (input: Request) => Promise<Response>;
  /**
   * A browser client whose session is in httpOnly cookies (R22 S8: the website, "web"):
   * every request carries the cookies (credentials "include"), a change says which client
   * it is (X-Session), and no request has an Authorization header. refreshAccessToken then
   * returns any non-null string when the session was refreshed. The apps leave it unset and
   * send their token.
   */
  session?: "web" | "admin";
  /**
   * R28: hears every request that failed: no answer at all (`error`), or an error status. Its
   * `id` is the X-Request-ID the client sent, which the API logs, so the app's log line can be
   * matched to the API's (or shown never to have reached it).
   */
  onFailure?: (failure: ApiFailure) => void;
}

/** R28: a failed request, as the client saw it. */
export interface ApiFailure {
  id: string;
  method: string;
  path: string;
  /** The answer's status; absent when no answer came (`error` says why). */
  status?: number;
  error?: string;
  /** How long it took, in ms. */
  ms: number;
}

/** A request id: random, short enough to read in a log line. */
export function newRequestId(): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (c?.randomUUID) return c.randomUUID();
  let id = "";
  for (let i = 0; i < 32; i++) id += Math.floor(Math.random() * 16).toString(16);
  return id;
}

export interface Api {
  core: Client<CorePaths>;
  realtime: Client<RealtimePaths>;
  worker: Client<WorkerPaths>;
}

/** An error from the API, with the human message the backend sent. */
export class ApiError extends Error {
  // Fields written out (not constructor parameter properties) so node --test can strip the types.
  status: number;
  code?: string;
  body?: unknown;
  constructor(status: number, message: string, code?: string, body?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.body = body;
  }
}

/** The message to show a person: the API's detail (string or {code, message}) or a fallback. */
export function errorMessage(body: unknown, fallback = "Something went wrong. Please try again."): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return fallback;
}

/**
 * Why POST /pricing/quote refused a bag (its 422 detail). `code` MIN_ORDER: the bag
 * is under the zone's minimum; `zone`, `amount` and `currency` are there for the
 * client to word it in its language and format the amount with its own formatter
 * (`message` is the English text). `tip_presets`: the city's tip buttons, sent once
 * the rules are known, so a refused bag still shows them.
 */
export interface QuoteRefusal {
  code: string;
  message: string;
  zone?: string | null;
  amount?: string | null;
  currency?: string | null;
  tip_presets?: CoreSchemas["TipPresetsOut"] | null;
  /** R27, code KITCHEN_CLOSED: why (availability's reason_code), when orders can next come in, on whose clock. */
  reason_code?: string | null;
  opens_at?: string | null;
  time_zone?: string | null;
  closed_note?: string | null;
}

/** The refusal in an error body from POST /pricing/quote, or null. */
export function quoteRefusal(body: unknown): QuoteRefusal | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return null;
  const d = detail as Partial<QuoteRefusal>;
  return typeof d.code === "string" ? { ...d, code: d.code, message: String(d.message ?? "") } : null;
}

/** Throw ApiError for a failed openapi-fetch result; return its data otherwise. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const body = result.error;
    const detail = (body as { detail?: { code?: string } } | null)?.detail;
    throw new ApiError(result.response.status, errorMessage(body), typeof detail === "object" ? detail?.code : undefined, body);
  }
  return result.data as T;
}

/** R27: the longest a request waits for a token refresh (the apps' refresh itself gives up at 15 s). */
export const REFRESH_WAIT_MS = 20000;

/** The token refresh didn't settle in time: the request fails (the person stays signed in). */
export class RefreshWaitError extends Error {
  constructor(ms: number) {
    super(`No new session in ${Math.round(ms / 1000)} s`);
    this.name = "RefreshWaitError";
  }
}

/** `p`, or a RefreshWaitError after `ms` (its timer is always cleared). */
function within<T>(p: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const late = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new RefreshWaitError(ms)), ms);
  });
  return Promise.race([p, late]).finally(() => clearTimeout(timer));
}

export function createApi(config: ApiConfig): Api {
  let refreshing: Promise<string | null> | null = null;
  // R27: an unread copy of each request that may need a retry after a 401. Sending a request reads
  // its body, and a request whose body was read can't be copied any more; rebuilding the retry from
  // the sent request threw ("already used"), so every POST after the 15-minute access token expired
  // failed once as "Can't reach BhojanGo" (the bag couldn't price or pay). Kept per request, freed
  // with it.
  const unsent = new WeakMap<Request, Request>();
  // R28: every request carries an X-Request-ID; a failure is reported with it (onFailure).
  const started = new WeakMap<Request, number>();
  const report = (request: Request, more: { status?: number; error?: string }) => {
    if (!config.onFailure) return;
    let path = request.url;
    try {
      path = new URL(request.url).pathname;
    } catch {
      /* keep the url */
    }
    config.onFailure({ id: request.headers.get("X-Request-ID") ?? "", method: request.method, path,
      ms: Date.now() - (started.get(request) ?? Date.now()), ...more });
  };
  const trace: Middleware = {
    onRequest({ request }) {
      // Not from a browser session (the website, admin): a custom header would make every read
      // a CORS preflight. Their requests still get an id from the API (its response says it).
      if (!config.session && !request.headers.has("X-Request-ID")) request.headers.set("X-Request-ID", newRequestId());
      started.set(request, Date.now());
      return request;
    },
    onResponse({ request, response }) {
      if (response.status >= 400) report(request, { status: response.status });
      return undefined;
    },
    onError({ request, error }) {
      report(request, { error: error instanceof Error ? `${error.name}: ${error.message}` : String(error) });
    },
  };
  const auth: Middleware = {
    onRequest({ request }) {
      if (config.session) {
        // Reads go as "simple" requests (no CORS preflight before each one): core_api takes the
        // website's cookie for them. A change names its client, which core_api requires (CSRF).
        if (request.method !== "GET" && request.method !== "HEAD") request.headers.set("X-Session", config.session);
        return request;
      }
      const token = config.getAccessToken();
      if (token && !request.headers.has("Authorization")) request.headers.set("Authorization", `Bearer ${token}`);
      if (config.refreshAccessToken && request.method !== "GET" && request.method !== "HEAD") unsent.set(request, request.clone());
      return request;
    },
    // Return nothing to keep the response as it is (openapi-fetch's contract).
    async onResponse({ request, response }) {
      if (response.status !== 401 || !config.refreshAccessToken || request.headers.get("X-Retried") === "1") return undefined;
      if (request.url.includes("/auth/")) return undefined; // sign-in and refresh answer 401 themselves
      // One refresh shared by concurrent requests; cleared once it settles, and never awaited
      // longer than refreshWaitMs: a refresh that hangs fails this request instead of freezing
      // it and every request after it (R27, the kitchen board's silent stall).
      if (!refreshing) {
        const shared: Promise<string | null> = within(Promise.resolve().then(() => config.refreshAccessToken!()),
          config.refreshWaitMs ?? REFRESH_WAIT_MS).finally(() => {
          if (refreshing === shared) refreshing = null;
        });
        refreshing = shared;
      }
      const token = await refreshing;
      if (!token) {
        config.onSignedOut?.();
        return undefined;
      }
      const retry = new Request(unsent.get(request) ?? request, { headers: new Headers(request.headers) });
      unsent.delete(request);
      if (!config.session) retry.headers.set("Authorization", `Bearer ${token}`);
      retry.headers.set("X-Retried", "1");
      // The retry is its own request in the API's log: the first id with "-r".
      const first = request.headers.get("X-Request-ID");
      if (first) retry.headers.set("X-Request-ID", `${first}-r`);
      started.set(retry, Date.now());
      try {
        return await (config.fetch ?? fetch)(retry);
      } catch (e) {
        report(retry, { error: e instanceof Error ? `${e.name}: ${e.message}` : String(e) });
        throw e;
      }
    },
  };
  const custom = {
    ...(config.fetch ? { fetch: config.fetch } : {}),
    ...(config.session ? { credentials: "include" as const } : {}),
  };
  const core = createClient<CorePaths>({ baseUrl: config.coreUrl, ...custom });
  const realtime = createClient<RealtimePaths>({ baseUrl: config.realtimeUrl, ...custom });
  const worker = createClient<WorkerPaths>({ baseUrl: config.workerUrl, ...custom });
  // trace first: it sees the final answer, after auth's retry (middleware answers run in reverse).
  for (const c of [core, realtime, worker] as Client<never>[]) c.use(trace, auth);
  return { core, realtime, worker };
}
