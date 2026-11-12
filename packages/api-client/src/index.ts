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
  /** Called when the session can't be refreshed (sign the person out). */
  onSignedOut?: () => void;
}

export interface Api {
  core: Client<CorePaths>;
  realtime: Client<RealtimePaths>;
  worker: Client<WorkerPaths>;
}

/** An error from the API, with the human message the backend sent. */
export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string, public body?: unknown) {
    super(message);
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

/** Throw ApiError for a failed openapi-fetch result; return its data otherwise. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const body = result.error;
    const detail = (body as { detail?: { code?: string } } | null)?.detail;
    throw new ApiError(result.response.status, errorMessage(body), typeof detail === "object" ? detail?.code : undefined, body);
  }
  return result.data as T;
}

export function createApi(config: ApiConfig): Api {
  let refreshing: Promise<string | null> | null = null;
  const auth: Middleware = {
    onRequest({ request }) {
      const token = config.getAccessToken();
      if (token && !request.headers.has("Authorization")) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
    // Return nothing to keep the response as it is (openapi-fetch's contract).
    async onResponse({ request, response }) {
      if (response.status !== 401 || !config.refreshAccessToken || request.headers.get("X-Retried") === "1") return undefined;
      if (request.url.includes("/auth/")) return undefined; // sign-in and refresh answer 401 themselves
      refreshing = refreshing ?? config.refreshAccessToken().finally(() => { refreshing = null; });
      const token = await refreshing;
      if (!token) {
        config.onSignedOut?.();
        return undefined;
      }
      const retry = new Request(request, { headers: new Headers(request.headers) });
      retry.headers.set("Authorization", `Bearer ${token}`);
      retry.headers.set("X-Retried", "1");
      return fetch(retry);
    },
  };
  const core = createClient<CorePaths>({ baseUrl: config.coreUrl });
  const realtime = createClient<RealtimePaths>({ baseUrl: config.realtimeUrl });
  const worker = createClient<WorkerPaths>({ baseUrl: config.workerUrl });
  for (const c of [core, realtime, worker] as Client<never>[]) c.use(auth);
  return { core, realtime, worker };
}
