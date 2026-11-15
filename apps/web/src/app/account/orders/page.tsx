import type { Metadata } from "next";
import { Suspense } from "react";

import { getContext } from "@/lib/prefs";
import { OrdersView } from "./OrdersView";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("account.orders.meta_title") };
}

export default function OrdersPage() {
  return (
    <Suspense>
      <OrdersView />
    </Suspense>
  );
}
