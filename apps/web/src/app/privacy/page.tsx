// /privacy: the published document for the visitor's country (R8 F10; components/legal/LegalPages.tsx).
import { CurrentLegalPage, legalMetadata, type Search } from "@/components/legal/LegalPages";

export const generateMetadata = () => legalMetadata("privacy");

export default async function Page({ searchParams }: { searchParams: Search }) {
  return <CurrentLegalPage kind="privacy" searchParams={searchParams} />;
}
