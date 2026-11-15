import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { FavouritesView } from "./FavouritesView";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("favourites.meta_title") };
}

export default function FavouritesPage() {
  return <FavouritesView />;
}
