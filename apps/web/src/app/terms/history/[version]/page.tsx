// /terms/history/N: one published version, current or replaced (R8 F10).
import { LegalVersionPage, legalMetadata, type Search } from "@/components/legal/LegalPages";

export const generateMetadata = () => legalMetadata("terms");

export default async function Page({ params, searchParams }: { params: Promise<{ version: string }>; searchParams: Search }) {
  return <LegalVersionPage kind="terms" version={(await params).version} searchParams={searchParams} />;
}
