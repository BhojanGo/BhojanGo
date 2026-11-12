"use client";
// Edit a rule's settings as a form (never JSON): numbers, text, yes/no, lists
// of rows (distance slabs, time windows), tiers and lists of amounts. The
// backend checks the result against the rule's template before saving.
import { useState } from "react";

type V = unknown;

function label(k: string): string {
  const words: Record<string, string> = { up_to: "Up to", per_unit: "Per km/mi", beyond_per_unit: "Beyond the last slab, per km/mi (empty = not delivered)" };
  return words[k] ?? k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function Field({ k, v, onChange }: { k: string; v: V; onChange: (v: V) => void }) {
  if (typeof v === "boolean") {
    return <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={v} onChange={(e) => onChange(e.target.checked)} /> {label(k)}</label>;
  }
  if (Array.isArray(v) && v.every((x) => typeof x === "object" && x !== null)) {
    const rows = v as Record<string, V>[];
    const keys = Object.keys(rows[0] ?? {});
    return (
      <fieldset className="space-y-2">
        <legend className="text-sm font-bold">{label(k)}</legend>
        {rows.map((row, i) => (
          <div key={i} className="flex flex-wrap items-end gap-2 rounded-xl bg-porcelain p-2">
            {keys.map((rk) => <Field key={rk} k={rk} v={row[rk]} onChange={(nv) => onChange(rows.map((r, j) => (j === i ? { ...r, [rk]: nv } : r)))} />)}
            <button type="button" onClick={() => onChange(rows.filter((_, j) => j !== i))} className="h-9 rounded-full px-3 text-sm font-bold text-chili">Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => onChange([...rows, { ...(rows[rows.length - 1] ?? {}) }])} className="h-9 rounded-full border border-line-strong px-3 text-sm font-bold">+ Add a row</button>
      </fieldset>
    );
  }
  if (Array.isArray(v)) {
    return (
      <label className="block text-sm font-bold">{label(k)} <span className="font-normal text-muted">(separate with commas)</span>
        <input defaultValue={(v as V[]).join(", ")} onChange={(e) => onChange(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
          className="mt-1 block h-10 w-full rounded-lg border border-line px-2 font-normal" />
      </label>
    );
  }
  if (v && typeof v === "object") {
    const entries = Object.entries(v as Record<string, V>);
    return (
      <fieldset className="space-y-1">
        <legend className="text-sm font-bold">{label(k)}</legend>
        <div className="flex flex-wrap gap-2">
          {entries.map(([ek, ev]) => <Field key={ek} k={k === "tiers" ? `Tier ${ek}` : ek} v={ev} onChange={(nv) => onChange({ ...(v as object), [ek]: nv })} />)}
        </div>
      </fieldset>
    );
  }
  return (
    <label className="block text-sm font-bold">{label(k)}
      <input value={v == null ? "" : String(v)} placeholder="not set" onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
        className="mt-1 block h-10 w-40 rounded-lg border border-line px-2 font-normal" />
    </label>
  );
}

export function RuleEditor({ params, onSave, onCancel, busy, saveLabel }: {
  params: Record<string, V>; onSave: (p: Record<string, V>) => void; onCancel: () => void; busy: boolean; saveLabel: string;
}) {
  const [draft, setDraft] = useState<Record<string, V>>(params);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        {Object.entries(draft).map(([k, v]) => <Field key={k} k={k} v={v} onChange={(nv) => setDraft((d) => ({ ...d, [k]: nv }))} />)}
      </div>
      <div className="flex gap-2">
        <button type="button" onClick={() => onSave(draft)} disabled={busy} className="h-10 rounded-full bg-peacock px-4 font-extrabold text-white">{saveLabel}</button>
        <button type="button" onClick={onCancel} className="h-10 rounded-full border border-line-strong px-4 font-bold">Cancel</button>
      </div>
      <p className="text-xs text-muted">Checked against the rule&apos;s template before anything is saved.</p>
    </div>
  );
}
