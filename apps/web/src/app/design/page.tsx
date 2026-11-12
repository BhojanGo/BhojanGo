"use client";

import { useState } from "react";
import {
  Badge, Button, Card, Chip, FairBill, Input, Logo, LogoMark, PlateImage, ScopeBar, Segmented, Sheet, Spinner,
  StatusPill, TabBar, ORDER_STATUS,
} from "@bhojango/ui";
import { color, dark } from "@bhojango/ui/tokens";

// The component gallery (P16): every design-system component with the
// worked example's data, for design review. Not linked from the site.

const BILL = [
  { code: "food", label: "Food", amount: "560.00" },
  { code: "promotion", label: "Code BHOJAN10", amount: "-50.00", funded_by: "platform" },
  { code: "delivery_fee", label: "Delivery · 4.2 km", amount: "35.00" },
  { code: "promotion", label: "Free delivery", amount: "-35.00", funded_by: "restaurant" },
  { code: "packaging", label: "Packaging", amount: "10.00" },
  { code: "service_fee", label: "Service fee", amount: "11.20" },
  { code: "surge", label: "Busy-hour fee · till 9:30", amount: "15.00" },
  { code: "tax", label: "GST", amount: "30.72" },
  { code: "tip", label: "Tip", amount: "20.00" },
];

const STATES = [
  { code: "IN-AP", name: "Andhra Pradesh", cities: [{ code: "IN-AP-VJA", name: "Vijayawada", status: "draft" }, { code: "IN-AP-VSK", name: "Visakhapatnam", status: "draft" }] },
  { code: "IN-TG", name: "Telangana", cities: [{ code: "IN-TG-HYD", name: "Hyderabad", status: "live" }, { code: "IN-TG-WGL", name: "Warangal", status: "draft" }] },
];

const Icon = ({ d }: { d: string }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><path d={d} /></svg>
);

export default function DesignGallery() {
  const [tip, setTip] = useState("20");
  const [chip, setChip] = useState("Biryani");
  const [sheet, setSheet] = useState(false);
  const [tab, setTab] = useState("home");
  const [country, setCountry] = useState("IN");
  const [state, setState] = useState<string | null>(null);
  const [city, setCity] = useState<string | null>("IN-TG-HYD");

  return (
    <main className="mx-auto flex max-w-content flex-col gap-8 px-8 py-12">
      <header className="flex items-center justify-between">
        <Logo suffix="design system" />
        <span className="text-sm text-muted">P16 · tokens and components from the design board</span>
      </header>

      <Section title="Colour">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Object.entries(color).map(([k, v]) => <Swatch key={k} name={k} value={v} />)}
        </div>
        <h3 className="mt-4 text-sm font-bold">Rider (dark)</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Object.entries(dark).map(([k, v]) => <Swatch key={k} name={k} value={v} />)}
        </div>
      </Section>

      <Section title="Type">
        <p className="font-display text-[34px] font-semibold leading-[1.05] tracking-[-1px]">Good evening, Srini.</p>
        <p className="font-display text-2xl font-semibold tracking-[-0.5px]">Your bag</p>
        <p className="text-base">Slow-cooked basmati, saffron and fried onion, sealed and steamed for two hours.</p>
        <p className="text-xs font-bold uppercase tracking-[1.2px] text-muted">Tonight&apos;s table</p>
      </Section>

      <Section title="Buttons and chips">
        <div className="flex flex-wrap items-center gap-3">
          <Button size="lg">Pay ₹596.92</Button>
          <Button variant="secondary">Details</Button>
          <Button variant="ghost">Change</Button>
          <Button variant="rider">Accept order</Button>
          <Button loading>Placing order</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {["Biryani", "Dosa", "Thali", "Pizza"].map((c) => <Chip key={c} selected={chip === c} onClick={() => setChip(c)}>{c}</Chip>)}
          <Chip count={4}>Needs attention</Chip>
        </div>
        <div className="max-w-sm">
          <Segmented label="Tip your rider" value={tip} onChange={setTip}
            options={[{ value: "0", label: "None" }, { value: "10", label: "₹10" }, { value: "20", label: "₹20" }, { value: "30", label: "₹30" }]} />
        </div>
      </Section>

      <Section title="Cards, plate, status">
        <div className="grid gap-6 sm:grid-cols-2">
          <Card padding="none" className="overflow-hidden">
            <PlateImage alt="Hyderabadi Dum Biryani" className="h-[118px]" />
            <div className="p-4">
              <div className="font-display text-xl font-semibold tracking-[-0.3px]">Spice Route Kitchen</div>
              <div className="mt-1 text-sm text-muted"><b className="text-kohl">4.6</b> · Hyderabadi · 25–30 min · 2.1 km</div>
              <div className="mt-3 flex gap-2"><Badge variant="dark">Free delivery · kitchen&apos;s treat</Badge><Badge variant="kesar">20% off</Badge></div>
            </div>
          </Card>
          <Card tone="outline" padding="lg" className="flex flex-col gap-3">
            {Object.keys(ORDER_STATUS).map((s) => <StatusPill key={s} status={s} />)}
          </Card>
        </div>
      </Section>

      <Section title="The fair bill">
        <div className="max-w-sm"><FairBill lines={BILL} currency="INR" /></div>
      </Section>

      <Section title="Inputs and sheet">
        <div className="grid max-w-xl gap-4">
          <Input shape="pill" aria-label="Search" placeholder="Dishes, kitchens, cravings" />
          <Input label="Phone number" placeholder="98765 43210" hint="We'll text you a 6-digit code." />
          <Input label="FSSAI licence" defaultValue="1234" error="14 digits: check the number on your licence." />
          <Button variant="secondary" onClick={() => setSheet(true)}>Open the customise sheet</Button>
        </div>
        <Sheet open={sheet} onClose={() => setSheet(false)} title="Chicken Dum Biryani"
          footer={<Button size="lg" block onClick={() => setSheet(false)}>Add to bag · ₹340</Button>}>
          <p className="text-sm text-muted">Pick a size, spice level and add-ons.</p>
        </Sheet>
      </Section>

      <Section title="Tab bar">
        <div className="flex justify-center rounded-card bg-porcelain p-6">
          <TabBar current={tab} onSelect={setTab} items={[
            { key: "home", label: "Home", icon: <Icon d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" /> },
            { key: "search", label: "Search", icon: <Icon d="M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM21 21l-4.3-4.3" /> },
            { key: "orders", label: "Orders", icon: <Icon d="M6 3h12l1 18H5zM9 7a3 3 0 0 0 6 0" /> },
            { key: "account", label: "Account", icon: <Icon d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0" /> },
          ]} />
        </div>
      </Section>

      <Section title="Scope bar (admin)">
        <ScopeBar showAll country={country} onCountry={setCountry} state={state} onState={setState} city={city} onCity={setCity}
          countries={[{ code: "IN", name: "India", badge: 4 }, { code: "US", name: "United States", badge: 2, badgeTone: "alert" }]}
          states={country === "IN" ? STATES : []} className="rounded-card border border-line" />
      </Section>

      <Section title="Logo">
        <div className="flex items-center gap-6">
          <LogoMark size={64} />
          <span className="rounded-card bg-peacock p-3"><LogoMark size={64} tone="white" /></span>
          <Spinner size="lg" />
        </div>
      </Section>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-display text-[22px] font-semibold tracking-[-0.4px]">{title}</h2>
      {children}
    </section>
  );
}

function Swatch({ name, value }: { name: string; value: string }) {
  return (
    <div className="overflow-hidden rounded-card border border-line bg-white">
      <div className="h-14" style={{ background: value }} />
      <div className="px-3 py-2 text-xs"><b>{name}</b> <span className="text-muted">{value}</span></div>
    </div>
  );
}
