"use client";
// "Print / Save as PDF": the browser's print dialog with the clean print stylesheet
// (no header, footer, contents or buttons; the draft banner stays).
export function PrintButton({ label }: { label: string }) {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      data-testid="legal-print"
      className="inline-flex h-11 items-center gap-2 rounded-full border border-line-strong bg-white px-4 text-label font-semibold text-kohl hover:border-peacock hover:text-peacock print:hidden"
    >
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 9V3h12v6" /><rect x="6" y="14" width="12" height="7" rx="1" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      </svg>
      {label}
    </button>
  );
}
