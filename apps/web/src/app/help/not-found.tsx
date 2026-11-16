// An article or topic that isn't there (moved, renamed or unpublished): search and the topics.
import Link from "next/link";

import { HelpSearch } from "@/components/help/HelpSearch";
import { TopicIcon } from "@/components/help/parts";
import { PageWidth } from "@/components/help/states";
import { TOPICS } from "@/lib/help";
import { getContext } from "@/lib/prefs";

export default async function HelpNotFound() {
  const { t } = await getContext();
  return (
    <div className="bg-porcelain pb-16">
      <PageWidth className="pt-10">
        <div className="mx-auto max-w-2xl space-y-6 rounded-card bg-white p-6 sm:p-10">
          <div className="space-y-2">
            <h1 className="text-h1 text-kohl">{t("helpcentre.not_found_title")}</h1>
            <p className="text-body text-muted">{t("helpcentre.not_found_body")}</p>
          </div>
          <HelpSearch />
          <ul className="grid gap-2 sm:grid-cols-2">
            {TOPICS.map((topic) => (
              <li key={topic}>
                <Link href={`/help/${topic}`} className="flex min-h-[48px] items-center gap-3 rounded-xl px-3 text-label font-semibold text-kohl hover:bg-porcelain">
                  <span className="text-peacock"><TopicIcon topic={topic} size={20} /></span>
                  {t(`helpcentre.topics.${topic}.title`)}
                </Link>
              </li>
            ))}
          </ul>
          <Link href="/help" className="inline-flex h-12 items-center rounded-pill bg-peacock px-6 text-label font-bold text-white">{t("helpcentre.back_to_help")}</Link>
        </div>
      </PageWidth>
    </div>
  );
}
