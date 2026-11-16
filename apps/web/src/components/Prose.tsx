// A readable page of sections (help, terms, privacy).
import type { ReactNode } from "react";

export function Prose({ title, updated, intro, sections }: {
  title: string; updated?: string; intro?: ReactNode; sections: { id: string; title: string; body: ReactNode }[];
}) {
  return (
    <div className="container-page grid gap-10 py-12 md:grid-cols-[240px_1fr]">
      <nav aria-label="On this page" className="hidden md:block">
        <ul className="sticky top-24 space-y-2 text-small">
          {sections.map((s) => <li key={s.id}><a href={`#${s.id}`} className="text-muted hover:text-peacock">{s.title}</a></li>)}
        </ul>
      </nav>
      <article className="max-w-3xl space-y-8">
        <header className="space-y-2">
          <h1 className="text-display">{title}</h1>
          {updated ? <p className="text-small text-muted">Last updated {updated}</p> : null}
          {intro ? <div className="text-body-lg text-muted">{intro}</div> : null}
        </header>
        {sections.map((s) => (
          <section key={s.id} id={s.id} className="scroll-mt-24 space-y-3 rounded-card bg-white p-6 leading-relaxed">
            <h2 className="text-h3">{s.title}</h2>
            <div className="space-y-3 text-body">{s.body}</div>
          </section>
        ))}
      </article>
    </div>
  );
}
