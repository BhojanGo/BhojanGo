"use client";
// A small menu that opens below its button and closes on Escape or a click outside.
import { useEffect, useRef, useState, type ReactNode } from "react";

export function Popover({
  button,
  children,
  align = "right",
  width = 260,
  label,
}: {
  button: (open: boolean, toggle: () => void) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
  width?: number;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div ref={ref} className="relative shrink-0">
      {button(open, () => setOpen((o) => !o))}
      {open && (
        <div
          role="menu"
          aria-label={label}
          style={{ width }}
          className={`absolute top-[calc(100%+8px)] z-50 rounded-2xl border border-[#E2E7E8] bg-white p-2 text-[15px] shadow-[0_16px_40px_rgba(17,20,24,0.16)] ${align === "right" ? "right-0" : "left-0"}`}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

/** A row in a menu: 44 px, the chosen one tinted with a tick. */
export function MenuRow({ selected, onClick, children, href }: { selected?: boolean; onClick?: () => void; children: ReactNode; href?: string }) {
  const cls = `flex h-11 w-full items-center justify-between rounded-[10px] px-[14px] text-left ${
    selected ? "bg-[#EFF6F6] font-extrabold text-[#083F46]" : "text-[#111418] hover:bg-[#F4F6F6]"
  }`;
  const tick = <span className="text-[13px] text-[#4C5A5E]">{selected ? "✓" : ""}</span>;
  if (href) {
    return (
      <a role="menuitem" href={href} className={cls}>
        <span>{children}</span>
        {tick}
      </a>
    );
  }
  return (
    <button type="button" role="menuitemradio" aria-checked={!!selected} onClick={onClick} className={cls}>
      <span>{children}</span>
      {tick}
    </button>
  );
}

export function MenuTitle({ children }: { children: ReactNode }) {
  return <div className="px-[14px] pb-[6px] pt-2 text-xs font-extrabold uppercase tracking-[1px] text-[#4C5A5E]">{children}</div>;
}

export function MenuNote({ children }: { children: ReactNode }) {
  return <div className="mt-[6px] border-t border-[#EEF1F1] px-[14px] pb-1 pt-[10px] text-xs text-[#4C5A5E]">{children}</div>;
}
