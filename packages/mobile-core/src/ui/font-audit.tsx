// Dev only: the font audit's route marker. With EXPO_PUBLIC_FONT_AUDIT=1 the type
// tokens record every size read while a screen renders and Metro shows
//   FONT_AUDIT /orders 12,14,15,18,30
// once per screen (tools/mobile/font_sizes.py collects them). Each root layout renders
//   {fontAuditEnabled ? <FontAudit usePathname={usePathname} /> : null}
// so with the flag off (the default, and every release build) nothing runs at all.
import { setAuditRoute } from "./type";

export function FontAudit({ usePathname }: { usePathname: () => string }) {
  // Set during render, before the new screen (a later sibling) renders its text.
  setAuditRoute(usePathname());
  return null;
}
