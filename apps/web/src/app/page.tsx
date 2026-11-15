// Placeholder until the home page is rebuilt (web v2, WebLanding / WebHome).
import { getContext } from "@/lib/prefs";

export default async function Home() {
  const { t } = await getContext();
  return <h1 className="p-16 font-display text-5xl">{t("common.tagline")}</h1>;
}
