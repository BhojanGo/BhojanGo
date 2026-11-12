"use client";
// The header's right side: the bag (with its count) and sign in / your orders.
import Link from "next/link";

import { useBag, useHydrated, useSession } from "@/lib/client";

export function HeaderActions() {
  const ready = useHydrated();
  const count = useBag((s) => s.lines.reduce((n, l) => n + l.quantity, 0));
  const user = useSession((s) => s.user);
  return (
    <div className="flex items-center gap-3 text-sm font-bold">
      {ready && user ? <Link href="/orders" className="hidden px-2 hover:text-peacock sm:block">Your orders</Link> : null}
      {ready && !user ? <Link href="/sign-in" className="px-2 hover:text-peacock">Sign in</Link> : null}
      <Link href="/checkout" aria-label={`Bag, ${ready ? count : 0} items`}
        className="inline-flex h-11 items-center gap-2 rounded-pill bg-peacock px-5 text-white hover:bg-peacock-deep">
        Bag <span className="rounded-pill bg-white/20 px-2 tabular-nums">{ready ? count : 0}</span>
      </Link>
    </div>
  );
}
