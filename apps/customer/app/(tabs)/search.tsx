// Search the kitchens that deliver to the drop point (names, cuisines, areas),
// from the same /discover answer as home; the cuisine row filters too.
import { color, Input, space, Txt, useI18n } from "@bhojango/mobile-core";
import { useMemo, useState } from "react";
import { FlatList, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CuisineRow } from "../../components/HomeSections";
import { KitchenCard } from "../../components/KitchenCard";
import { cuisineTiles, ofCuisine } from "../../lib/contract";
import { useDiscover } from "../../lib/restaurants";
import { useWhere } from "../../lib/where";
import { TabEnd, useTabBarSpace } from "../../lib/tabbar";

export default function Search() {
  const { t } = useI18n();
  const bottom = useTabBarSpace();
  const point = useWhere((s) => s.point);
  const market = useWhere((s) => s.market);
  const { data, kitchens } = useDiscover(market?.serviceable ? point : null);
  const [q, setQ] = useState("");
  const [cuisine, setCuisine] = useState<string | null>(null);
  const tiles = useMemo(() => cuisineTiles(data?.cuisines, kitchens), [data, kitchens]);
  const needle = q.trim().toLocaleLowerCase();
  const results = ofCuisine(kitchens, cuisine).filter(
    (k) => !needle || [k.name, k.area ?? "", ...k.cuisine_types, ...k.tags].join(" ").toLocaleLowerCase().includes(needle),
  );
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <View style={{ padding: space[5], gap: space[4] }}>
        <Txt variant="h2" accessibilityRole="header">{t("tabs.search")}</Txt>
        <Input testID="search-input" shape="pill" placeholder={t("common.search_placeholder")} value={q} onChangeText={setQ} autoFocus
          accessibilityLabel={t("common.search_label")} />
      </View>
      <FlatList
        data={results}
        keyExtractor={(k) => k.id}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={<View style={{ marginTop: -space[8], marginBottom: space[4], marginHorizontal: -space[5] }}><CuisineRow tiles={tiles} selected={cuisine} onSelect={setCuisine} /></View>}
        contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingBottom: bottom }}
        ListEmptyComponent={
          <View testID="search-last">
            <Txt style={{ color: color.muted }}>{needle ? t("app.search.no_match", { q: q.trim() }) : kitchens.length ? t("home.no_filter_match") : t("home.no_kitchens")}</Txt>
          </View>
        }
        ListFooterComponent={<TabEnd tab="search" />}
        renderItem={({ item, index }) => (
          <View testID={index === results.length - 1 ? "search-last" : undefined}>
            <KitchenCard k={item} currency={data?.currency} unit={data?.distance_unit} compact />
          </View>
        )}
      />
    </SafeAreaView>
  );
}
