// "Test site: demo kitchens, no real orders or payments" on every console page outside
// production (QA, staging, make dev). A slim strip in the page flow above everything else.
import { showTestBanner } from "@bhojango/ui/environment";

export function TestSiteBanner() {
  if (!showTestBanner(process.env.APP_ENV)) return null;
  return (
    <div
      role="note"
      data-testid="test-site-banner"
      className="border-b border-[#D4932A] bg-[#F6E7CC] px-4 py-[6px] text-center text-[13px] font-semibold leading-[18px] text-kohl"
    >
      Test site: demo kitchens, no real orders or payments
    </div>
  );
}
