// Search kitchens and dishes near the drop point (matches names, cuisines and menu text).
import { color, Input, space, textFont, Txt } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useRestaurants } from "../../lib/restaurants";
import { useWhere } from "../../lib/where";

export default function Search() {
  const market = useWhere((s) => s.market);
  const { items } = useRestaurants(market?.serviceable ? market.city_name : null);
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const results = needle
    ? items.filter((r) => [r.name, r.description, ...r.cuisine_types].join(" ").toLowerCase().includes(needle))
    : items;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <View style={{ padding: space[5], gap: space[4] }}>
        <Txt variant="h1" accessibilityRole="header">Search</Txt>
        <Input shape="pill" placeholder="Dishes, kitchens, cravings" value={q} onChangeText={setQ} autoFocus accessibilityLabel="Search" />
      </View>
      <FlatList
        data={results}
        keyExtractor={(r) => r.id}
        contentContainerStyle={{ paddingHorizontal: space[5], gap: space[3], paddingBottom: 120 }}
        ListEmptyComponent={<Txt style={{ color: color.muted }}>Nothing matches “{q}” nearby.</Txt>}
        renderItem={({ item }) => (
          <Pressable accessibilityRole="button" onPress={() => router.push(`/restaurant/${item.id}`)}
            style={{ backgroundColor: color.white, borderRadius: 16, padding: space[4], gap: 4 }}>
            <Txt variant="title">{item.name}</Txt>
            <Text style={[textFont("400"), { color: color.muted, fontSize: 14 }]}>{item.cuisine_types.join(" · ")}</Text>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}
