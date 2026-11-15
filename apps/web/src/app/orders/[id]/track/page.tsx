// /orders/{id}/track (WebTracking, MWebTracking): the live order.
import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { Tracking } from "./Tracking";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("track.title"), robots: { index: false, follow: false } };
}

export default async function TrackPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Tracking id={id} />;
}
