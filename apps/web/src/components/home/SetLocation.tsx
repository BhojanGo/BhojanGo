"use client";
// "Set your delivery location" (R8): the location line's button where we don't serve
// the visitor's place, or know nothing about it. It opens the address box.
import { useCallback, useState } from "react";

import { AddressDialog } from "@/components/AddressDialog";

export function SetLocation({ label, country }: { label: string; country: string | null }) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      <button
        type="button"
        data-testid="set-location"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
        className="inline-flex min-h-11 items-center font-semibold text-[#0B5D66] underline-offset-4 hover:underline"
      >
        {label}
      </button>
      {open && <AddressDialog title={label} country={country} onClose={close} />}
    </>
  );
}
