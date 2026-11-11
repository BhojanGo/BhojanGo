/**
 * JWT authentication middleware.
 *
 * Verifies the HS256 access tokens issued by user-svc using only Node's built-in
 * crypto (no extra dependency) so the same JWT_SECRET protects every service.
 */
import { createHmac, timingSafeEqual } from "crypto";
import { NextFunction, Request, Response } from "express";

import { JWT_CONFIG } from "../../config";

export interface AuthedRequest extends Request {
  user?: { userId: string; role: string; country: string };
}

function base64UrlToBuffer(input: string): Buffer {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/");
  return Buffer.from(padded, "base64");
}

/** Returns the decoded payload if the token is a valid, unexpired access token, else null. */
export function verifyAccessToken(token: string, secret: string): Record<string, unknown> | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [headerB64, payloadB64, signatureB64] = parts;

  const expected = createHmac("sha256", secret).update(`${headerB64}.${payloadB64}`).digest();
  const actual = base64UrlToBuffer(signatureB64);
  if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) {
    return null;
  }

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(base64UrlToBuffer(payloadB64).toString("utf8"));
  } catch {
    return null;
  }

  const exp = payload["exp"];
  if (typeof exp === "number" && Date.now() / 1000 >= exp) return null;
  if (payload["type"] !== "access") return null;
  if (!payload["sub"]) return null;

  return payload;
}

export function authenticate(req: AuthedRequest, res: Response, next: NextFunction): void {
  const header = req.headers.authorization ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) {
    res.status(401).json({ error: "Missing or malformed Authorization header" });
    return;
  }

  const payload = verifyAccessToken(token, JWT_CONFIG.secret);
  if (!payload) {
    res.status(401).json({ error: "Invalid or expired token" });
    return;
  }

  req.user = {
    userId: String(payload["sub"]),
    role: String(payload["role"] ?? "customer"),
    country: String(payload["country"] ?? "US"),
  };
  next();
}

/** Restricts a route to the given roles. Must be used after `authenticate`. */
export function requireRole(...roles: string[]) {
  return (req: AuthedRequest, res: Response, next: NextFunction): void => {
    if (!req.user || !roles.includes(req.user.role)) {
      res.status(403).json({ error: "Forbidden" });
      return;
    }
    next();
  };
}
