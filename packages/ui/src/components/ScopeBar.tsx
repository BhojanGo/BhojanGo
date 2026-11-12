import * as React from "react";
import { cn } from "../lib/utils";

export interface ScopeCountry {
  code: string;
  name: string;
  badge?: number;
  badgeTone?: "attention" | "alert";
}

export interface ScopeState {
  code: string;
  name: string;
  cities: { code: string; name: string; status?: string }[];
}

export interface ScopeBarProps {
  countries: ScopeCountry[];
  /** "*" = All countries; only for people with platform scope */
  country: string;
  onCountry: (code: string) => void;
  showAll?: boolean;
  states?: ScopeState[];
  state?: string | null;
  onState?: (code: string | null) => void;
  city?: string | null;
  onCity?: (code: string | null) => void;
  className?: string;
}

/** Admin scope: country tabs, then state chips, then a city picker grouped by
 * state (AdminHome.html, AdminCountry.html). Pass in only the scopes the admin may see. */
export function ScopeBar(p: ScopeBarProps) {
  const states = p.states ?? [];
  return (
    <div className={cn("bg-white", p.className)}>
      <nav aria-label="Country" className="flex flex-wrap gap-1 overflow-x-auto border-b border-line px-8">
        {p.showAll && (
          <CountryTab active={p.country === "*"} onClick={() => p.onCountry("*")}>
            All countries
          </CountryTab>
        )}
        {p.countries.map((c) => (
          <CountryTab key={c.code} active={p.country === c.code} onClick={() => p.onCountry(c.code)}>
            <span className="rounded-[6px] bg-line-divider px-1.5 py-0.5 text-[11px] font-extrabold text-kohl">{c.code}</span>
            {c.name}
            {c.badge ? (
              <span
                className={cn(
                  "inline-flex h-5 min-w-5 items-center justify-center rounded-pill px-1 text-[11px] font-extrabold",
                  c.badgeTone === "alert" ? "bg-chili text-white" : "bg-kesar text-kohl",
                )}
              >
                {c.badge}
              </span>
            ) : null}
          </CountryTab>
        ))}
      </nav>
      {p.country !== "*" && states.length > 0 && (
        <nav aria-label="State and city" className="flex flex-wrap items-center gap-2 px-8 py-3">
          <StateChip active={!p.state} onClick={() => p.onState?.(null)}>
            All states
          </StateChip>
          {states.map((s) => (
            <StateChip key={s.code} active={p.state === s.code} onClick={() => p.onState?.(s.code)}>
              {s.name} · {s.cities.length}
            </StateChip>
          ))}
          <div className="ml-auto">
            <CityPicker
              states={p.state ? states.filter((s) => s.code === p.state) : states}
              value={p.city ?? null}
              onChange={(c) => p.onCity?.(c)}
            />
          </div>
        </nav>
      )}
    </div>
  );
}

function CountryTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "box-border flex h-[52px] items-center gap-2 border-b-[3px] px-4 text-[15px]",
        active ? "border-peacock font-extrabold text-peacock-deep" : "border-transparent font-semibold text-muted hover:text-kohl",
      )}
    >
      {children}
    </button>
  );
}

function StateChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "h-9 rounded-pill border px-3.5 text-sm",
        active ? "border-peacock bg-peacock-tint font-extrabold text-peacock-deep" : "border-line bg-white font-semibold text-kohl hover:border-line-strong",
      )}
    >
      {children}
    </button>
  );
}

/** Searchable city list, grouped under each state's name. */
export function CityPicker({ states, value, onChange }: {
  states: ScopeState[];
  value: string | null;
  onChange: (code: string | null) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState("");
  const listId = React.useId();
  const all = states.flatMap((s) => s.cities.map((c) => ({ ...c, state: s.name })));
  const matches = all.filter((c) => c.name.toLowerCase().includes(q.toLowerCase()));
  const current = all.find((c) => c.code === value);
  const choose = (code: string | null) => {
    onChange(code);
    setOpen(false);
  };
  return (
    <div className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-10 items-center gap-2 rounded-pill border border-line-strong bg-white px-4 text-sm font-bold"
      >
        {current ? current.name : "All cities"}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-card bg-white p-3 shadow-float">
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search cities"
            aria-controls={listId}
            className="h-10 w-full rounded-pill bg-porcelain px-4 text-sm outline-none"
          />
          <ul id={listId} role="listbox" aria-label="Cities" className="mt-2 max-h-72 overflow-y-auto">
            <li role="option" aria-selected={!value}>
              <button type="button" className="w-full rounded-chip px-3 py-2 text-left text-sm hover:bg-porcelain" onClick={() => choose(null)}>
                All cities
              </button>
            </li>
            {matches.map((c, i) => (
              <li key={c.code} role="option" aria-selected={c.code === value}>
                {(i === 0 || c.state !== matches[i - 1]?.state) && (
                  <div className="px-3 pb-1 pt-2 text-xs font-bold uppercase tracking-wide text-muted">{c.state}</div>
                )}
                <button
                  type="button"
                  onClick={() => choose(c.code)}
                  className={cn("w-full rounded-chip px-3 py-2 text-left text-sm hover:bg-porcelain", c.code === value && "font-extrabold text-peacock-deep")}
                >
                  {c.name}
                  {c.status && c.status !== "live" ? <span className="ml-2 text-xs text-muted">{c.status}</span> : null}
                </button>
              </li>
            ))}
            {matches.length === 0 && <li className="px-3 py-2 text-sm text-muted">No city matches</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
