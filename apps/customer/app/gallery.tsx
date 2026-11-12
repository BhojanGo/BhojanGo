// The mobile component gallery (P16): every design-system component on a
// phone, for design review. Open it at bhojango://gallery (not linked in the app).
import {
  Button, Card, Chip, color, dark, FairBill, Input, LogoMark, PlateImage, Segmented, Sheet, StatusPill, TabBar, Txt,
} from "@bhojango/mobile-core";
import { useState } from "react";
import { ScrollView, View } from "react-native";
import Svg, { Path } from "react-native-svg";

const BILL = [
  { code: "food", label: "Food", amount: "560.00" },
  { code: "promotion", label: "Code BHOJAN10", amount: "-50.00", funded_by: "platform" },
  { code: "delivery_fee", label: "Delivery · 4.2 km", amount: "35.00" },
  { code: "promotion", label: "Free delivery", amount: "-35.00", funded_by: "restaurant" },
  { code: "packaging", label: "Packaging", amount: "10.00" },
  { code: "service_fee", label: "Service fee", amount: "11.20" },
  { code: "tax", label: "GST", amount: "30.72" },
  { code: "tip", label: "Tip", amount: "20.00" },
];

function icon(d: string) {
  return function TabIcon(c: string) {
    return (
      <Svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth={2} strokeLinecap="round">
        <Path d={d} />
      </Svg>
    );
  };
}

export default function Gallery() {
  const [tip, setTip] = useState("20");
  const [chip, setChip] = useState("Biryani");
  const [sheet, setSheet] = useState(false);
  const [tab, setTab] = useState("home");
  return (
    <ScrollView style={{ backgroundColor: color.porcelain }} contentContainerStyle={{ padding: 20, gap: 32, paddingBottom: 64 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12, marginTop: 32 }}>
        <LogoMark size={40} />
        <Txt variant="h1">Design system</Txt>
      </View>

      <View style={{ gap: 12 }}>
        <Txt variant="h2">Colour</Txt>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {[...Object.values(color), ...Object.values(dark)].map((v, i) => (
            <View key={i} style={{ width: 40, height: 40, borderRadius: 8, backgroundColor: v, borderWidth: 1, borderColor: color.line }} />
          ))}
        </View>
      </View>

      <View style={{ gap: 8 }}>
        <Txt variant="hero">Good evening, Srini.</Txt>
        <Txt variant="hero" style={{ color: color.muted }}>What&apos;s for dinner?</Txt>
        <Txt variant="eyebrow" style={{ color: color.muted }}>Tonight&apos;s table</Txt>
        <Txt>Slow-cooked basmati, saffron and fried onion, sealed and steamed for two hours.</Txt>
      </View>

      <View style={{ gap: 12 }}>
        <Txt variant="h2">Buttons and chips</Txt>
        <Button title="Pay ₹596.92" size="lg" block />
        <Button title="Details" variant="secondary" />
        <Button title="Accept order" variant="rider" block />
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {["Biryani", "Dosa", "Thali", "Pizza"].map((c) => <Chip key={c} label={c} selected={chip === c} onPress={() => setChip(c)} />)}
        </View>
        <Segmented label="Tip your rider" value={tip} onChange={setTip}
          options={[{ value: "0", label: "None" }, { value: "10", label: "₹10" }, { value: "20", label: "₹20" }, { value: "30", label: "₹30" }]} />
      </View>

      <View style={{ gap: 12 }}>
        <Txt variant="h2">Card, plate, status</Txt>
        <Card padded={false}>
          <PlateImage label="Hyderabadi Dum Biryani" />
          <View style={{ padding: 16, gap: 4 }}>
            <Txt variant="title">Spice Route Kitchen</Txt>
            <Txt variant="small" style={{ color: color.muted }}>4.6 · Hyderabadi · 25–30 min · 2.1 km</Txt>
          </View>
        </Card>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {["placed", "preparing", "picked_up", "delivered", "cancelled"].map((s) => <StatusPill key={s} status={s} />)}
        </View>
      </View>

      <FairBill lines={BILL} currency="INR" />

      <View style={{ gap: 12 }}>
        <Txt variant="h2">Inputs and sheet</Txt>
        <Input shape="pill" placeholder="Dishes, kitchens, cravings" />
        <Input label="Phone number" placeholder="98765 43210" hint="We'll text you a 6-digit code." keyboardType="phone-pad" />
        <Button title="Open the customise sheet" variant="secondary" onPress={() => setSheet(true)} />
      </View>

      <Card tone="dark" style={{ gap: 12 }}>
        <Txt variant="title" style={{ color: dark.text }}>Rider (dark)</Txt>
        <Input dark label="Vehicle number" placeholder="TS 09 AB 7316" />
        <Button title="Go online" variant="rider" block />
      </Card>

      <TabBar current={tab} onSelect={setTab} items={[
        { key: "home", label: "Home", icon: icon("M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z") },
        { key: "search", label: "Search", icon: icon("M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM21 21l-4.3-4.3") },
        { key: "orders", label: "Orders", icon: icon("M6 3h12l1 18H5zM9 7a3 3 0 0 0 6 0") },
        { key: "account", label: "Account", icon: icon("M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0") },
      ]} />

      <Sheet visible={sheet} onClose={() => setSheet(false)} title="Chicken Dum Biryani"
        footer={<Button title="Add to bag · ₹340" size="lg" block onPress={() => setSheet(false)} />}>
        <Txt style={{ color: color.muted }}>Pick a size, spice level and add-ons.</Txt>
      </Sheet>
    </ScrollView>
  );
}
