"use client";
// Save (a favourite kitchen, signed in) and Share (the phone's share sheet, or
// copy the link) on the kitchen page.
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useFavourites } from "@/components/FavouriteHeart";
import { Heart, Share } from "@/components/Icons";
import { useHydrated, useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";

export function KitchenActions({ id, name, compact }: { id: string; name: string; compact?: boolean }) {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const router = useRouter();
  const path = usePathname();
  const { ids, load, toggle } = useFavourites();
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (hydrated && user) void load(user.id);
  }, [hydrated, user, load]);
  const saved = ids.has(`restaurant:${id}`);

  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: name, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // the person closed the share sheet
    }
  }

  const pill = compact
    ? "flex h-9 items-center gap-[6px] rounded-[10px] border border-[#E2E7E8] bg-white px-3 text-label text-[#111418]"
    : "inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-full border-[1.5px] border-[#C9D3D4] bg-white px-[22px] text-label text-[#111418] hover:border-[#0B5D66]";
  return (
    <span className="flex gap-[10px]">
      <button
        type="button"
        aria-pressed={saved}
        aria-label={saved ? t("common.unsave_kitchen", { name }) : t("common.save_kitchen", { name })}
        onClick={() => (user ? void toggle("restaurant", id) : router.push(`/signin?next=${encodeURIComponent(path)}`))}
        className={pill}
      >
        <Heart filled={saved} color={saved ? "#C0392B" : "#111418"} />
        {saved ? t("kitchen.saved") : t("kitchen.save")}
      </button>
      <button type="button" onClick={() => void share()} className={pill}>
        {compact && <Share size={14} />}
        {copied ? t("kitchen.link_copied") : t("kitchen.share")}
      </button>
      <span role="status" className="sr-only">{copied ? t("kitchen.link_copied") : ""}</span>
    </span>
  );
}
