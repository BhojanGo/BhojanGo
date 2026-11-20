export interface HeaderOptions {
  connect?: string[];
  img?: string[];
  script?: string[];
  style?: string[];
  frame?: string[];
  worker?: string[];
  geolocation?: boolean;
  popups?: boolean;
  payment?: string[];
}

/** The page's Content-Security-Policy; with a nonce, only scripts carrying it (and what they load) run. */
export declare function contentSecurityPolicy(o?: HeaderOptions, nonce?: string): string;
/** A fresh nonce for one response. */
export declare function newNonce(): string;
/** Every security header but the CSP (the proxy sets that one), for next.config. */
export declare function securityHeaders(o?: HeaderOptions): { key: string; value: string }[];
