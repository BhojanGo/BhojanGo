// /terms and /privacy (R8 F10): the document the admin published for the visitor's
// country (from location resolution, or ?country= from the switcher), in a 720 px
// reading column with a "Key points" box, a sticky table of contents built from the
// headings (collapsible on phones), "Last updated <date> · Version N", the version
// history and a print stylesheet. Every environment but production, and any draft,
// carries "Draft: pending legal review". Documents are English for now; the page
// chrome follows the visitor's language and says so.
import { parse, toc as contents, type Block } from "@bhojango/ui/legal-markdown";
import { isProduction } from "@bhojango/ui/environment";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Markdown } from "@/components/legal/Markdown";
import { PrintButton } from "@/components/legal/PrintButton";
import { TocLinks } from "@/components/legal/TocLinks";
import { date } from "@/lib/format";
import { getContext, type Context } from "@/lib/prefs";
import { legalDocument, legalHistory, legalVersion, type LegalKind, type LegalPage } from "@/lib/server";

export type Search = Promise<Record<string, string | string[] | undefined>>;

const PAGE = "container-page py-8 md:py-12 print:max-w-none print:p-0";

/** ?country=IN from the switcher, else the visitor's country (address, chosen city, IP hint, browser). */
async function countryFor(searchParams: Search, ctx: Context): Promise<string | null> {
  const asked = (await searchParams).country;
  if (typeof asked === "string" && /^[A-Za-z]{2}$/.test(asked)) return asked.toUpperCase();
  return ctx.country?.code ?? ctx.directory.countries[0]?.code ?? null;
}

function countryName(ctx: Context, code: string): string {
  try {
    const name = new Intl.DisplayNames([ctx.language, "en"], { type: "region" }).of(code);
    if (name && name !== code) return name;
  } catch {
    /* an old runtime: fall back to Markets' name */
  }
  return ctx.directory.countries.find((c) => c.code === code)?.name ?? code;
}

const day = (ctx: Context, iso?: string | null) =>
  iso ? date(iso.slice(0, 10), ctx.formatLocale, null, { day: "numeric", month: "long", year: "numeric" }) : "";

function showDraft(doc: LegalPage | null): boolean {
  return !isProduction(process.env.APP_ENV) || doc?.status === "draft" || !doc || doc.status === "unavailable";
}

function DraftBanner({ text }: { text: string }) {
  return (
    <div role="note" data-testid="legal-draft-banner"
      className="mb-6 flex items-center gap-3 rounded-card border border-kesar bg-[#FBF4E6] px-4 py-3 text-label font-semibold text-kohl print:mb-4 print:border-2">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8A5A12" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
        <path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      </svg>
      {text}
    </div>
  );
}

function CountrySwitch({ ctx, kind, current, countries, history }: {
  ctx: Context; kind: LegalKind; current: string; countries: string[]; history?: boolean;
}) {
  const all = countries.includes(current) ? countries : [...countries, current];
  if (all.length < 2) return null;
  return (
    <nav aria-label={ctx.t("legal.country")} className="mb-6 flex flex-wrap items-center gap-2 print:hidden" data-testid="legal-countries">
      <span className="mr-1 text-label text-muted">{ctx.t("legal.country")}</span>
      {all.map((c) => (
        <Link key={c} href={`/${kind}${history ? "/history" : ""}?country=${c}`} aria-current={c === current ? "page" : undefined}
          className={`inline-flex h-10 items-center rounded-full px-4 text-label ${c === current
            ? "bg-kohl font-bold text-white" : "border border-line-strong bg-white font-semibold text-kohl hover:border-peacock"}`}>
          {countryName(ctx, c)}
        </Link>
      ))}
    </nav>
  );
}

function KeyPoints({ points, title }: { points: string[]; title: string }) {
  if (!points.length) return null;
  return (
    <section aria-labelledby="key-points" data-testid="legal-key-points"
      className="mt-8 rounded-card border border-[#B9D6D9] bg-[#EFF6F6] p-5 md:p-6 print:border-2 print:bg-white">
      <h2 id="key-points" className="text-h3 text-kohl">{title}</h2>
      <ul className="mt-3 space-y-3">
        {points.map((p, i) => (
          <li key={i} className="flex gap-3 text-body leading-relaxed text-[#24383B]">
            <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0B5D66" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="mt-[3px] shrink-0">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            <span>{p}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Unavailable({ ctx, kind, country, doc }: { ctx: Context; kind: LegalKind; country: string | null; doc: LegalPage | null }) {
  const document = ctx.t(`legal.${kind}`);
  const others = (doc?.available_countries ?? []).filter((c) => c !== country);
  return (
    <div className={PAGE}>
      <div className="mx-auto max-w-[720px]">
        <DraftBanner text={ctx.t("legal.draft_banner")} />
        <h1 className="text-h1 text-kohl">{document}</h1>
        <p className="mt-4 text-body-lg text-[#24383B]" data-testid="legal-unavailable">
          {ctx.t("legal.unavailable", { document, country: country ? countryName(ctx, country) : "—" })}
        </p>
        {others.length ? (
          <div className="mt-8 rounded-card bg-porcelain p-5">
            <p className="text-label font-semibold text-kohl">{ctx.t("legal.unavailable_others")}</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {others.map((c) => (
                <li key={c}><Link href={`/${kind}?country=${c}`} className="inline-flex h-11 items-center rounded-full border border-line-strong bg-white px-4 text-label font-semibold text-kohl hover:border-peacock">{countryName(ctx, c)}</Link></li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** The document itself (the current version or an older one). */
function DocumentView({ ctx, kind, doc, blocks }: { ctx: Context; kind: LegalKind; doc: LegalPage; blocks: Block[] }) {
  const items = contents(blocks);
  const older = doc.status === "superseded";
  const historyHref = `/${kind}/history?country=${doc.country}`;
  const contentsLabel = ctx.t("legal.contents");
  return (
    <div className={PAGE}>
      <p className="mb-4 hidden text-h3 font-bold text-peacock print:block">{ctx.t("common.brand")}</p>
      {showDraft(doc) ? <div className="mx-auto max-w-[1024px] print:max-w-none"><DraftBanner text={ctx.t("legal.draft_banner")} /></div> : null}
      <div className="lg:grid lg:grid-cols-[240px_minmax(0,720px)] lg:justify-center lg:gap-16 print:block">
        <aside className="hidden lg:block print:hidden">
          <nav aria-label={contentsLabel} className="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pb-6" data-testid="legal-toc">
            <p className="mb-2 px-3 text-caption text-muted">{contentsLabel}</p>
            <TocLinks items={items} spy />
          </nav>
        </aside>
        <article className="min-w-0 max-w-[720px] print:max-w-none" data-testid="legal-document">
          <CountrySwitch ctx={ctx} kind={kind} current={doc.country} countries={doc.available_countries} />
          {older ? (
            <div role="note" className="mb-6 rounded-card border border-line-strong bg-porcelain px-4 py-3 text-body" data-testid="legal-older">
              {ctx.t("legal.older", { version: String(doc.version ?? ""), date: day(ctx, doc.superseded_at) })}{" "}
              <Link href={`/${kind}?country=${doc.country}`} className="font-semibold text-peacock underline underline-offset-2 print:hidden">{ctx.t("legal.older_current")}</Link>
            </div>
          ) : null}
          <h1 className="text-h1 text-kohl">{doc.title}</h1>
          <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-body text-muted" data-testid="legal-meta">
            <span>{ctx.t("legal.updated", { date: day(ctx, doc.effective_date ?? doc.published_at) })}</span>
            <span aria-hidden="true">·</span>
            <span>{ctx.t("legal.version", { version: String(doc.version ?? "") })}</span>
            <span aria-hidden="true" className="hidden sm:inline print:hidden">·</span>
            <Link href={historyHref} className="font-semibold text-peacock underline underline-offset-2 hover:text-peacock-deep print:hidden">{ctx.t("legal.history")}</Link>
            <span className="hidden print:inline">· {countryName(ctx, doc.country)}</span>
          </p>
          {doc.language !== ctx.language ? <p className="mt-2 text-small text-muted" data-testid="legal-english-only" lang={ctx.language}>{ctx.t("legal.english_only")}</p> : null}
          <div className="mt-5"><PrintButton label={ctx.t("legal.print")} /></div>
          <div lang={doc.language}>
            <KeyPoints points={doc.key_points} title={ctx.t("legal.key_points")} />
            <details className="group mt-6 rounded-card border border-line bg-white lg:hidden print:hidden" data-testid="legal-toc-mobile">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-label font-semibold text-kohl [&::-webkit-details-marker]:hidden">
                {contentsLabel}
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 transition-transform group-open:rotate-180"><path d="m6 9 6 6 6-6" /></svg>
              </summary>
              <nav aria-label={contentsLabel} className="border-t border-line px-1 py-2"><TocLinks items={items} /></nav>
            </details>
            <div className="mt-10"><Markdown blocks={blocks} /></div>
          </div>
        </article>
      </div>
    </div>
  );
}

export async function legalMetadata(kind: LegalKind): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t(`legal.${kind}`), alternates: { canonical: `/${kind}` } };
}

export async function CurrentLegalPage({ kind, searchParams }: { kind: LegalKind; searchParams: Search }) {
  const ctx = await getContext();
  const country = await countryFor(searchParams, ctx);
  const doc = country ? await legalDocument(kind, country, ctx.language) : null;
  if (!doc || doc.status === "unavailable") return <Unavailable ctx={ctx} kind={kind} country={country} doc={doc} />;
  return <DocumentView ctx={ctx} kind={kind} doc={doc} blocks={parse(doc.body)} />;
}

export async function LegalVersionPage({ kind, version, searchParams }: { kind: LegalKind; version: string; searchParams: Search }) {
  const ctx = await getContext();
  const country = await countryFor(searchParams, ctx);
  const n = Number(version);
  if (!country || !Number.isInteger(n) || n < 1) notFound();
  const doc = await legalVersion(kind, country, n, ctx.language);
  if (!doc) notFound();
  return <DocumentView ctx={ctx} kind={kind} doc={doc} blocks={parse(doc.body)} />;
}

export async function LegalHistoryPage({ kind, searchParams }: { kind: LegalKind; searchParams: Search }) {
  const ctx = await getContext();
  const country = await countryFor(searchParams, ctx);
  const history = country ? await legalHistory(kind, country, ctx.language) : null;
  const document = ctx.t(`legal.${kind}`);
  const name = country ? countryName(ctx, country) : "—";
  const versions = history?.versions ?? [];
  return (
    <div className={PAGE}>
      <div className="mx-auto max-w-[720px]">
        {showDraft(null) ? <DraftBanner text={ctx.t("legal.draft_banner")} /> : null}
        {country ? <CountrySwitch ctx={ctx} kind={kind} current={country} countries={history?.available_countries ?? []} history /> : null}
        <h1 className="text-h1 text-kohl">{ctx.t("legal.history_title", { document })}</h1>
        <p className="mt-3 text-body-lg text-muted">
          {versions.length ? ctx.t("legal.history_intro", { country: name }) : ctx.t("legal.history_empty", { country: name })}
        </p>
        <ol className="mt-8 space-y-4" data-testid="legal-history">
          {versions.map((v) => {
            const current = v.status === "published";
            const href = current ? `/${kind}?country=${country}` : `/${kind}/history/${v.version}?country=${country}`;
            return (
              <li key={v.version} className="rounded-card border border-line bg-white p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-h3 text-kohl">{ctx.t("legal.version", { version: String(v.version) })}</h2>
                  {current
                    ? <span className="rounded-full bg-[#DDEBEC] px-2.5 py-0.5 text-small font-semibold text-[#083F46]">{ctx.t("legal.history_current")}</span>
                    : <span className="rounded-full bg-porcelain px-2.5 py-0.5 text-small text-muted">{ctx.t("legal.history_replaced", { date: day(ctx, v.superseded_at) })}</span>}
                </div>
                <p className="mt-2 text-body text-[#24383B]">{v.title} · {ctx.t("legal.history_effective", { date: day(ctx, v.effective_date ?? v.published_at) })}</p>
                {v.summary_of_changes ? <p className="mt-1 text-body text-muted">{ctx.t("legal.changes", { summary: v.summary_of_changes })}</p> : null}
                <Link href={href} className="mt-3 inline-flex h-11 items-center font-semibold text-peacock underline underline-offset-2 hover:text-peacock-deep">
                  {ctx.t("legal.history_read", { version: String(v.version) })}
                </Link>
              </li>
            );
          })}
        </ol>
        <p className="mt-8"><Link href={`/${kind}${country ? `?country=${country}` : ""}`} className="font-semibold text-peacock underline underline-offset-2">{ctx.t("legal.back", { document })}</Link></p>
      </div>
    </div>
  );
}
