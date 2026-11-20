// Next 16 proxy (was middleware), R22 security review (S9): a fresh nonce for every page of
// the console and the Content-Security-Policy that only lets scripts carrying it run (no
// 'unsafe-inline'). Next reads the nonce from the request's CSP header and puts it on its
// own scripts; the root layout reads the request, so every page is rendered with its own.
import { contentSecurityPolicy, newNonce } from "@bhojango/ui/security-headers";
import { NextResponse, type NextRequest } from "next/server";

// Sentry (R19): the browser sends error reports to the DSN's host, only when a DSN is set.
const SENTRY = (() => {
  try {
    return process.env.NEXT_PUBLIC_SENTRY_DSN ? [new URL(process.env.NEXT_PUBLIC_SENTRY_DSN).origin] : [];
  } catch {
    return [];
  }
})();

// The console talks to the services through its own /api rewrites ('self');
// the dispatch map draws OpenStreetMap tiles.
const ADMIN_CSP = { img: ["https://tile.openstreetmap.org"], connect: SENTRY };

export function proxy(request: NextRequest) {
  const nonce = newNonce();
  const csp = contentSecurityPolicy(ADMIN_CSP, nonce);
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  // pages only: not the API rewrites, Next's assets or the icons
  matcher: ["/((?!api/|_next/|favicon|icon|apple-icon).*)"],
};
