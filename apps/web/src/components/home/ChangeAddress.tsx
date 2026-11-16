"use client";
// "Wrong address? Try another address": opens the address box in place.
import { useState } from "react";

import { AddressBox } from "@/components/AddressBox";
import { useT } from "@/lib/i18n";

export function ChangeAddress({ country, children }: { country: string | null; children?: React.ReactNode }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <div>
      <p className="mt-4 text-body text-muted">
        {t("home.wrong_address")}{" "}
        <button type="button" aria-expanded={open} aria-controls="change-address" onClick={() => setOpen((o) => !o)} className="font-bold text-[#0B5D66] hover:text-[#083F46]">
          {t("home.try_another")}
        </button>
        {children}
      </p>
      {open && (
        <div id="change-address" className="mt-4 max-w-[600px]">
          <AddressBox size="sheet" country={country} autoFocus onPicked={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}
