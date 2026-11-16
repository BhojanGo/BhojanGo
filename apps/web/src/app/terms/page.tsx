// /terms: the published document for the visitor's country (R8 F10; components/legal/LegalPages.tsx).
import { CurrentLegalPage, legalMetadata, type Search } from "@/components/legal/LegalPages";

export const generateMetadata = () => legalMetadata("terms");

export default async function Page({ searchParams }: { searchParams: Search }) {
  return <CurrentLegalPage kind="terms" searchParams={searchParams} />;
}
