// A rule's settings form starts from every setting its template has (R17).

type V = unknown;

/** A rule template's JSON schema (GET /user/rules/templates params_schema), as far as the form needs it. */
export interface ParamsSchema { properties?: Record<string, { default?: V; description?: string; type?: string; anyOf?: { type?: string }[] }>; required?: string[] }

/** R17: every setting the rule's template has, not only the ones this version already has: a setting
 * added to the template later (R16 tax settings on an older rule) shows with its default; a required
 * number with no default starts empty ("not set"). Lists and nested settings are left as they are. */
export function withTemplateSettings(params: Record<string, V>, schema?: ParamsSchema): Record<string, V> {
  const out: Record<string, V> = { ...params };
  for (const [k, prop] of Object.entries(schema?.properties ?? {})) {
    if (k in out) continue;
    const d = prop.default;
    if (d === null || ["boolean", "number", "string"].includes(typeof d)) out[k] = d;
    else if (d === undefined && schema?.required?.includes(k)) {
      const types = [prop.type, ...(prop.anyOf ?? []).map((a) => a.type)];
      if (types.includes("number") || types.includes("integer") || types.includes("string")) out[k] = null;
    }
  }
  return out;
}
