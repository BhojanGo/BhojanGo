/**
 * Human-readable message from an API error. FastAPI's `detail` is sometimes a
 * string and sometimes `{ code, message }`; validation errors use
 * `{ error: { message } }`. Never return an object: React can't render it.
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: unknown } })?.response?.data as
    | { detail?: unknown; error?: { message?: unknown } }
    | undefined;
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && typeof (detail as { message?: unknown }).message === "string") {
    return (detail as { message: string }).message;
  }
  if (typeof data?.error?.message === "string") return data.error.message;
  return fallback;
}
