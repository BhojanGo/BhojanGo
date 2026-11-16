"use client";
// The address box in a dialog: the header's address pill and the location line's
// "Set your delivery location" open it (R8). Escape or a click outside closes it.
import { useEffect } from "react";

import { useT } from "@/lib/i18n";
import { AddressBox } from "./AddressBox";
import { Close } from "./Icons";

export function AddressDialog({ title, country, onClose }: { title: string; country: string | null; onClose: () => void }) {
  const t = useT();
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-[60] flex items-start justify-center bg-[rgba(17,20,24,0.4)] p-4 pt-[10vh]" onClick={onClose}>
      <div className="w-full max-w-[560px] rounded-3xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center">
          <h2 className="m-0 flex-grow text-h2">{title}</h2>
          <button type="button" aria-label={t("common.close")} onClick={onClose} className="flex h-11 w-11 items-center justify-center">
            <Close color="#3D4A4E" />
          </button>
        </div>
        <AddressBox size="sheet" country={country} autoFocus onPicked={onClose} />
      </div>
    </div>
  );
}
