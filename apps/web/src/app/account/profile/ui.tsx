// The profile page's building blocks (WebProfile): section cards, rows, buttons.
import type { ReactNode } from "react";

export const card = "scroll-mt-24 rounded-3xl border border-[#E2E7E8] px-5 py-5 md:px-7 md:py-6";
export const h2 = "font-display text-[22px] font-semibold tracking-[-0.4px]";
export const link = "shrink-0 font-bold text-[#0B5D66] hover:text-[#083F46] disabled:opacity-60";
export const input = "mt-1 block h-11 w-full rounded-xl border-[1.5px] border-[#C9D3D4] bg-white px-3 text-[15px] font-normal text-[#111418] focus:border-[#0B5D66] focus:outline-none";
export const primary = "flex h-11 shrink-0 items-center justify-center rounded-full bg-[#0B5D66] px-5 font-extrabold text-white hover:bg-[#083F46] disabled:opacity-60";
export const ghost = "flex h-11 shrink-0 items-center justify-center rounded-full border-[1.5px] border-[#C9D3D4] px-5 font-bold text-[#111418] hover:bg-[#F4F6F6] disabled:opacity-60";

/** A labelled row: label | value (+ note) | action. Phone: the label sits above. */
export function Row({ label, children, note, action }: { label: ReactNode; children: ReactNode; note?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-[#EEF1F1] py-4 md:flex-nowrap md:py-[18px]">
      <span className="w-full text-sm font-bold text-[#4C5A5E] md:w-[200px] md:shrink-0">{label}</span>
      <span className="min-w-0 flex-grow">
        <b className="block break-words text-base">{children}</b>
        {note && <span className="mt-[2px] block text-[13px] text-[#4C5A5E]">{note}</span>}
      </span>
      {action}
    </div>
  );
}
