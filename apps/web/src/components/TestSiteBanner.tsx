// "Test site: demo kitchens, no real orders or payments" on every page outside production
// (QA, staging, make dev). A slim strip above the header, in the page flow: it scrolls away
// with the page, so it never covers content, the sticky header or the phone tab bar.
import { showTestBanner } from "@bhojango/ui/environment";

export function TestSiteBanner({ text }: { text: string }) {
  if (!showTestBanner(process.env.APP_ENV)) return null;
  return (
    <div
      role="note"
      data-testid="test-site-banner"
      className="border-b border-[#D4932A] bg-[#F6E7CC] px-4 py-[6px] text-center text-label leading-[18px] text-[#111418] print:hidden"
    >
      {text}
    </div>
  );
}
