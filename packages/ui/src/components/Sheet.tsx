import * as React from "react";
import { cn } from "../lib/utils";

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

/** Bottom sheet on phones, centred dialog on wider screens; 24 px radius. */
export function Sheet({ open, onClose, title, children, footer }: SheetProps) {
  const ref = React.useRef<HTMLDialogElement>(null);
  React.useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}
      aria-label={title}
      className={cn(
        "m-0 mt-auto w-full max-w-none rounded-t-sheet bg-white p-0 text-kohl shadow-sheet backdrop:bg-kohl/40",
        "sm:m-auto sm:max-w-lg sm:rounded-sheet",
      )}
    >
      <div className="flex flex-col gap-4 p-6">
        <div className="mx-auto h-1 w-10 rounded-pill bg-line-strong sm:hidden" aria-hidden />
        <div className="flex items-center justify-between">
          <h2 className="font-display text-[22px] font-semibold tracking-[-0.4px]">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="flex h-11 w-11 items-center justify-center rounded-pill hover:bg-porcelain">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>
        {children}
        {footer}
      </div>
    </dialog>
  );
}
