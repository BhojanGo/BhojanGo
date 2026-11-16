// /terms/history: every published version for the country, newest first (R8 F10).
import { LegalHistoryPage, legalMetadata, type Search } from "@/components/legal/LegalPages";

export const generateMetadata = () => legalMetadata("terms");

export default async function Page({ searchParams }: { searchParams: Search }) {
  return <LegalHistoryPage kind="terms" searchParams={searchParams} />;
}
