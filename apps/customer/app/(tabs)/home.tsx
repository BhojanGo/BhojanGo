// CustomerHome.html (+ CustomerLoading.html while kitchens load).
import { Button, Card, color, Sheet, radius, space, textFont, Txt, useBag, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { PlateHeader } from "../../lib/plate";
import { Icon } from "../../lib/icons";
import { km, useRestaurants } from "../../lib/restaurants";
import { greeting, useWhere, type DropPoint } from "../../lib/where";
import { useTabBarSpace } from "../../lib/tabbar";

export default function Home() {
  const user = useSession((s) => s.user);
  const { point, market, status, locate, setPoint, goHere, saved } = useWhere();
  const [picking, setPicking] = useState<DropPoint[] | null>(null);
  const bagCount = useBag((s) => s.lines.reduce((n, l) => n + l.quantity, 0));

  useEffect(() => {
    if (status === "idle") void locate();
  }, [status, locate]);

  useEffect(() => {
    if (status === "ready" && market && !market.serviceable) router.replace("/out-of-area");
  }, [status, market]);

  const { items, loading } = useRestaurants(market?.serviceable ? market.city_name : null);
  const first = (user?.full_name ?? "").split(" ")[0];
  const hi = greeting(market?.timezone);
  const bottom = useTabBarSpace();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: bottom }}>
        <View style={styles.top}>
          <Pressable testID="where" accessibilityRole="button" accessibilityLabel="Delivery address" onPress={() => void saved().then(setPicking)} style={styles.where}>
            <Icon name="pin" size={20} stroke={color.peacock} />
            <Text style={[textFont("700"), { fontSize: 15, color: color.kohl }]}>{point?.label ?? (status === "failed" ? "Choose an address" : "Finding you…")}</Text>
            <Icon name="chevron" size={16} />
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="Account" onPress={() => router.push("/account")} style={styles.avatar}>
            <Text style={[textFont("700"), { fontSize: 14 }]}>{initials(user?.full_name)}</Text>
          </Pressable>
        </View>

        <View style={{ paddingHorizontal: space[5], paddingTop: space[4] }}>
          <Txt variant="hero" accessibilityRole="header">{hi.hello}{first ? `, ${first}.` : "."}</Txt>
          <Txt variant="hero" style={{ color: color.muted }}>{hi.ask}</Txt>
        </View>

        <Pressable accessibilityRole="search" onPress={() => router.push("/search")} style={styles.search}>
          <Icon name="search" size={20} stroke={color.muted} />
          <Text style={[textFont("400"), { fontSize: 16, color: color.muted }]}>Dishes, kitchens, cravings</Text>
        </Pressable>

        <View style={styles.banner}>
          <Text style={[textFont("700"), styles.eyebrow]}>TONIGHT&apos;S TABLE</Text>
          <Txt variant="h2" style={{ color: color.white, fontSize: 26, lineHeight: 28, marginTop: 8, maxWidth: 200 }}>
            {market?.city_name === "Boise" ? "Bowls and burgers, made to order" : "Hyderabadi classics, slow-cooked"}
          </Txt>
        </View>

        <View style={styles.sectionHead}>
          <Txt variant="h2">Near you</Txt>
        </View>

        {status === "failed" ? (
          <View style={{ paddingHorizontal: space[5], gap: space[3] }}>
            <Txt style={{ color: color.muted }}>We couldn&apos;t tell where you are. Choose an address or allow location.</Txt>
            <Button title="Choose an address" variant="secondary" onPress={() => void saved().then(setPicking)} />
          </View>
        ) : status !== "ready" || loading ? (
          <Loading near={market?.zone_name ?? point?.label?.split("· ")[1]} />
        ) : (
          <View style={{ gap: space[3], paddingHorizontal: space[5] }}>
            {items.length === 0 ? <Txt style={{ color: color.muted }}>No kitchens are open here right now.</Txt> : null}
            {items.map((r) => {
              const d = point ? km(point, r) : null;
              return (
                <Pressable key={r.id} accessibilityRole="button" accessibilityLabel={r.name} onPress={() => router.push(`/restaurant/${r.id}`)}>
                  <Card padded={false}>
                    <PlateHeader label={r.name} height={118}
                      badge={Number(r.delivery_fee) === 0 ? "Free delivery · kitchen's treat" : undefined} />
                    <View style={{ padding: space[4], gap: 4 }}>
                      <Txt variant="title">{r.name}</Txt>
                      <Text style={[textFont("400"), { fontSize: 14, color: color.muted }]}>
                        <Text style={[textFont("700"), { color: color.kohl }]}>★ {Number(r.rating ?? 0).toFixed(1)}</Text>
                        {" · "}{r.cuisine_types.slice(0, 1).join(", ")} · {r.delivery_time_min}–{r.delivery_time_max} min
                        {d != null ? ` · ${d.toFixed(1)} km` : ""}
                      </Text>
                    </View>
                  </Card>
                </Pressable>
              );
            })}
          </View>
        )}
      </ScrollView>
      <Sheet visible={picking != null} onClose={() => setPicking(null)} title="Deliver to">
        {(picking ?? []).map((p) => (
          <Pressable key={p.addressId ?? p.label} accessibilityRole="button" onPress={() => { setPicking(null); void setPoint(p); }} style={styles.pick}>
            <Icon name="pin" size={20} stroke={color.peacock} />
            <Text style={[textFont("600"), { fontSize: 15, flex: 1 }]}>{p.label}</Text>
          </Pressable>
        ))}
        <Button title="Use my current location" variant="secondary" block onPress={() => { setPicking(null); void goHere(); }} />
      </Sheet>
      {bagCount > 0 ? (
        <Pressable accessibilityRole="button" accessibilityLabel={`Bag, ${bagCount} items`} onPress={() => router.push("/bag")} style={styles.bagPill}>
          <Icon name="bag" size={18} stroke={color.white} />
          <Text style={[textFont("800"), { color: color.white, fontSize: 15 }]}>Bag · {bagCount}</Text>
        </Pressable>
      ) : null}
    </SafeAreaView>
  );
}

/** CustomerLoading.html: grey shapes where the cards will be, and what we're doing. */
function Loading({ near }: { near?: string | null }) {
  return (
    <View accessibilityLabel="Loading kitchens near you" style={{ paddingHorizontal: space[5], gap: space[3] }}>
      {[0, 1].map((i) => (
        <View key={i} style={{ backgroundColor: color.white, borderRadius: radius.card, overflow: "hidden" }}>
          <View style={{ height: 118, backgroundColor: color.divider }} />
          <View style={{ padding: space[4], gap: 8 }}>
            <View style={{ height: 18, width: "60%", borderRadius: 6, backgroundColor: color.divider }} />
            <View style={{ height: 12, width: "80%", borderRadius: 6, backgroundColor: color.divider }} />
          </View>
        </View>
      ))}
      <View style={{ flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", marginTop: space[2] }}>
        <ActivityIndicator color={color.peacock} />
        <Txt variant="small" style={{ color: color.muted }}>Finding kitchens near {near ?? "you"}</Txt>
      </View>
    </View>
  );
}

function initials(name?: string | null): string {
  return (name ?? "").split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("") || "·";
}

const styles = StyleSheet.create({
  top: { paddingHorizontal: space[5], paddingTop: space[4], flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  // Rounded, so the Android focus highlight (after a tap) follows the pill instead of a grey box.
  where: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, borderRadius: radius.pill, paddingHorizontal: 4, overflow: "hidden" },
  avatar: {
    width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1, borderColor: color.line, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center",
  },
  search: {
    marginHorizontal: space[5], marginTop: space[6], height: 54, borderRadius: radius.pill, backgroundColor: color.white,
    flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 18,
    borderWidth: 1, borderColor: color.line, // a hairline, not an Android elevation box
  },
  banner: { marginHorizontal: space[5], marginTop: space[6], height: 184, borderRadius: radius.sheet, backgroundColor: color.peacock, padding: space[6] },
  eyebrow: { fontSize: 12, letterSpacing: 1.2, color: "#F2C77A" },
  sectionHead: { paddingHorizontal: space[5], paddingTop: space[8], paddingBottom: space[3] },
  pick: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 48, borderBottomWidth: 1, borderBottomColor: color.divider },
  bagPill: {
    position: "absolute", right: space[5], bottom: 104, height: 48, paddingHorizontal: space[5], borderRadius: radius.pill,
    backgroundColor: color.peacock, flexDirection: "row", alignItems: "center", gap: 8,
  },
});
