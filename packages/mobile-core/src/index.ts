// Shared by the Expo apps (customer, rider; partner from P19).
export { api as legacyApi, realtimeApi as legacyRealtimeApi } from "./lib/api"; // rider app until P18
export { apiErrorMessage } from "./lib/errors";
export { useAuthStore } from "./store/auth";
export { useCartStore } from "./store/cart";

// Design system (P16): tokens, fonts and components; same tokens as @bhojango/ui on the web.
export * from "./ui/components";
export { useBrandFonts } from "./ui/fonts";
export { color, dark, displayFont, elevation, FONT_FILES, radius, space, textFont, touch, typeStyle } from "./ui/theme";
export { billRows, billTotal, money } from "@bhojango/ui/bill";

// P17: generated API client, session and bag (the rider app moves over in P18).
export { api, urls, useSession, wsUrl } from "./session";
export type { User } from "./session";
export { cartItems, defaultPicks, useBag } from "./bag";
export type { BagLine, OptionGroup, Pick } from "./bag";
export { ACTIVE_STATUSES, ApiError, errorMessage, unwrap } from "@bhojango/api-client";
export type { CoreSchemas, OrderStatus } from "@bhojango/api-client";
