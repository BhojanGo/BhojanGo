// R17: "Ordering in <city> is paused for now…" while an admin has paused ordering (incident tools),
// for the city the app is in (or everywhere, or the whole country). Checked every minute; orders already
// on their way carry on. Text in the app's language; the admin's note as written.
// R18: useOrderingPauses() also tells the bag, which then can't be paid for.
import { api, space, type, useI18n } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { orderingBlock } from "../lib/ordering";
import { useWhere } from "../lib/where";

export interface Pause { id: string; scope: string; area: string; note?: string | null }

/** The ordering pauses that cover the app's city now (every pause while the city isn't known yet). */
export function useOrderingPauses(): Pause[] {
  const city = useWhere((s) => s.market?.city_code ?? null);
  const [pauses, setPauses] = useState<Pause[]>([]);
  useEffect(() => {
    let live = true;
    const load = () => api.core.GET("/api/v1/incidents/ordering-pauses/active")
      .then((r) => { if (live && r.data) setPauses(r.data as unknown as Pause[]); }).catch(() => undefined);
    void load();
    const timer = setInterval(load, 60_000);
    return () => { live = false; clearInterval(timer); };
  }, []);
  return pauses.filter((p) => p.scope === "*" || (city ? city === p.scope || city.startsWith(`${p.scope}-`) : true));
}

/** R19: why this kitchen's dishes can't go in the bag now (worded), or null: the city's ordering
 *  paused, the kitchen closed for now (an incident), or the kitchen not open. */
export function useKitchenBlock(r: { is_open?: boolean | null; closed_for_now?: boolean | null } | null | undefined): string | null {
  const { t } = useI18n();
  const paused = useOrderingPauses().length > 0;
  if (!r) return paused ? t("kitchen.bag_paused") : null;
  const key = orderingBlock({ paused, closedForNow: r.closed_for_now, isOpen: r.is_open });
  return key ? t(key) : null;
}

export function PauseBanner() {
  const { t } = useI18n();
  const shown = useOrderingPauses();
  if (!shown.length) return null;
  return (
    <View accessibilityRole="alert" testID="ordering-paused">
      {shown.map((p) => (
        <Text key={p.id} style={[type.label, { backgroundColor: "#F1E3E1", color: "#8C1D18", paddingHorizontal: space[4], paddingVertical: space[2], textAlign: "center" }]}>
          {p.scope === "*" ? t("incident.paused_everywhere") : t("incident.paused_area", { area: p.area })}{p.note ? ` ${p.note}` : ""}
        </Text>
      ))}
    </View>
  );
}
