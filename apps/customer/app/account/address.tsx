// Add or edit a saved address (WebProfile's address form). The map pin comes
// from the areas Markets knows (search by name, as on the website) or from
// where the phone is ("Use my location", asked only when tapped); the country
// is the pin's (Markets). Then the street, city, state, postal code, a name
// (Home, Work) and delivery notes for the rider.
import { Button, color, Input, radius, SafeAreaView, space, type, useI18n } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, Switch, Text, View } from "react-native";

import { followAddress, listAddresses, pinHere, saveAddress, searchAreas, type Address, type Area, type Pin } from "../../lib/account";
import { ScreenBar, Section, ui } from "../../lib/account-ui";
import { Icon } from "../../lib/icons";

function PinPicker({ pin, onPin }: { pin: Pin | null; onPin: (p: Pin) => void }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ q: string; list: Area[] } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    clearTimeout(timer.current);
    const term = q.trim();
    if (term.length < 2) return;
    timer.current = setTimeout(() => {
      searchAreas(term)
        .then((list) => {
          setHits({ q: term, list });
          setProblem(list.length ? null : t("address.no_match"));
        })
        .catch(() => setProblem(t("common.error")));
    }, 250);
    return () => clearTimeout(timer.current);
  }, [q, t]);

  async function here() {
    setLocating(true);
    setProblem(null);
    try {
      onPin(await pinHere());
    } catch {
      setProblem(t("address.location_denied"));
    } finally {
      setLocating(false);
    }
  }

  const shown = q.trim().length >= 2 && hits?.q === q.trim() ? hits.list : [];
  return (
    <Section title={t("account.addresses.location")} note={t("account.addresses.location_hint")} testID="pin-picker">
      <Input testID="area-search" shape="pill" value={q} onChangeText={setQ} placeholder={t("account.addresses.search_area")} accessibilityLabel={t("account.addresses.search_area")} />
      {shown.map((a, i) => (
        <Pressable key={`${a.label}-${a.lat}-${a.lng}`} testID={`area-${i}`} accessibilityRole="button"
          onPress={() => { onPin({ lat: a.lat, lng: a.lng, country: a.country, label: a.label, city: a.city_name }); setQ(""); }}
          style={({ pressed }) => [{ flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44, paddingHorizontal: 8, borderRadius: 10 }, pressed && { backgroundColor: color.peacockMist }]}>
          <Icon name="pin" size={18} stroke={color.muted} />
          <Text style={[type.label, { color: color.kohl, flex: 1 }]}>{a.label}</Text>
        </Pressable>
      ))}
      <Pressable testID="use-my-location" accessibilityRole="button" onPress={here} disabled={locating}
        style={{ flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, opacity: locating ? 0.6 : 1 }}>
        <Icon name="map" size={18} stroke={color.peacock} />
        <Text style={[type.label, { color: color.peacock }]}>{locating ? t("address.locating") : t("address.use_my_location")}</Text>
      </Pressable>
      {pin ? (
        <View testID="pin-set" style={{ flexDirection: "row", alignItems: "center", gap: 8, padding: space[3], borderRadius: radius.card, backgroundColor: color.peacockMist }}>
          <Icon name="pin" size={18} stroke={color.peacockDeep} />
          <Text style={[type.label, { color: color.peacockDeep, flex: 1 }]}>{t("account.addresses.location_set", { place: pin.label })}</Text>
        </View>
      ) : null}
      {problem ? <Text accessibilityRole="alert" style={ui.muted}>{problem}</Text> : null}
    </Section>
  );
}

function AddressForm({ address }: { address: Address | null }) {
  const { t } = useI18n();
  const [label, setLabel] = useState(address?.label ?? "");
  const [street, setStreet] = useState(address?.street ?? "");
  const [city, setCity] = useState(address?.city ?? "");
  const [state, setState] = useState(address?.state ?? "");
  const [postal, setPostal] = useState(address?.postal_code ?? "");
  const [notes, setNotes] = useState(address?.delivery_notes ?? "");
  const [isDefault, setIsDefault] = useState(!!address?.is_default);
  const [pin, setPin] = useState<Pin | null>(
    address && address.lat != null && address.lng != null ? { lat: address.lat, lng: address.lng, country: address.country, label: address.street } : null,
  );
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function onPin(p: Pin) {
    setPin(p);
    // Fill what the pin knows into empty fields; never overwrite what was typed.
    if (p.city && !city.trim()) setCity(p.city);
    if (p.state && !state.trim()) setState(p.state);
    if (p.postal && !postal.trim()) setPostal(p.postal);
    if (p.street && !street.trim()) setStreet(p.street);
  }

  async function save() {
    if (!pin) return setProblem(t("account.addresses.location_needed"));
    if (!street.trim() || !city.trim()) return setProblem(t("app.addresses.required"));
    setBusy(true);
    setProblem(null);
    try {
      const saved = await saveAddress(address?.id ?? null, {
        label: label.trim() || undefined, street: street.trim(), city: city.trim(), state: state.trim(), postal_code: postal.trim(),
        country: pin.country, lat: pin.lat, lng: pin.lng, delivery_notes: notes.trim() || null, is_default: isDefault,
      });
      if (isDefault) followAddress(saved);
      router.back();
    } catch (e) {
      const m = e instanceof Error ? e.message : "";
      setProblem(m && !m.startsWith("HTTP") ? m : t("account.profile.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <ScrollView contentContainerStyle={[ui.scroll, { paddingBottom: 140 }]} keyboardShouldPersistTaps="handled">
        <PinPicker pin={pin} onPin={onPin} />
        <Section>
          <Input testID="address-label" label={t("account.addresses.label")} value={label} onChangeText={setLabel} maxLength={50} />
          <Input testID="address-street" label={t("account.addresses.street")} value={street} onChangeText={setStreet} maxLength={500} autoComplete="street-address" />
          <Input testID="address-city" label={t("account.addresses.city")} value={city} onChangeText={setCity} maxLength={100} />
          <Input testID="address-state" label={t("account.addresses.state")} value={state} onChangeText={setState} maxLength={100} />
          <Input testID="address-postal" label={t("account.addresses.postal_code")} value={postal} onChangeText={setPostal} maxLength={20} autoComplete="postal-code" />
          <Input testID="address-notes" label={t("account.addresses.notes")} value={notes} onChangeText={setNotes} maxLength={500} multiline />
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 48 }}>
            <Text style={[type.label, { color: color.kohl, flex: 1 }]}>{t("account.addresses.make_default")}</Text>
            <Switch testID="address-default-switch" accessibilityLabel={t("account.addresses.make_default")} value={isDefault} onValueChange={setIsDefault}
              trackColor={{ true: color.peacock, false: color.lineStrong }} thumbColor={color.white} />
          </View>
        </Section>
        {problem ? <Text accessibilityRole="alert" style={ui.error}>{problem}</Text> : null}
      </ScrollView>
      <View style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: space[5], backgroundColor: color.white, borderTopWidth: 1, borderTopColor: color.line }}>
        <Button testID="save-address" title={t("common.save")} size="lg" block loading={busy} onPress={save} />
      </View>
    </>
  );
}

export default function AddressScreen() {
  const { t } = useI18n();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [address, setAddress] = useState<Address | null | "missing">(id ? null : "missing");

  useEffect(() => {
    if (!id) return;
    listAddresses().then((all) => setAddress(all.find((a) => a.id === id) ?? "missing")).catch(() => setAddress("missing"));
  }, [id]);

  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right", "bottom"]}>
      <ScreenBar title={id ? t("account.addresses.edit_title") : t("account.addresses.new_title")} fallback="/account/addresses" testID="address-form-title" />
      {id && address === null ? <Text style={[ui.muted, { padding: space[5] }]}>{t("account.loading")}</Text> : (
        <AddressForm key={address === "missing" ? "new" : address?.id} address={address === "missing" ? null : address} />
      )}
    </SafeAreaView>
  );
}
