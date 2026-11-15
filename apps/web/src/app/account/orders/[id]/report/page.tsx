import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { ReportView } from "./ReportView";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("account.report.meta_title") };
}

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReportView id={id} />;
}
