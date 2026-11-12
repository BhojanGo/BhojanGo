import type { Metadata } from "next";

import { Prose } from "@/components/Prose";

export const metadata: Metadata = { title: "Privacy", description: "What BhojanGo collects, why, who sees it, and your choices." };

export default function Privacy() {
  return (
    <Prose
      title="Privacy notice"
      updated="November 2026"
      intro="What we collect when you order, why, who sees it, and how to delete it."
      sections={[
        { id: "collect", title: "What we collect", body: <p>Your phone number and name, the addresses you deliver to (with their location on the map), your orders and payments (we never see full card numbers: the payment provider handles them), and messages you send support.</p> },
        { id: "use", title: "Why", body: <p>To take and deliver your orders, show you the bill, send you order updates (push, SMS for the important moments, and email receipts), handle refunds, prevent fraud, and meet tax and consumer law.</p> },
        { id: "share", title: "Who sees it", body: <>
          <p>The kitchen sees your first name and what you ordered. Your rider sees your first name and initial, and your address only after they pick up your food. Payment providers (Razorpay in India, Stripe in the US) process your payment. We don&apos;t sell your data.</p>
        </> },
        { id: "location", title: "Location", body: <p>If you choose &quot;Use my location&quot; at checkout, your browser shares it once to find where to deliver. Riders share their location only while they&apos;re online, so you can follow your order.</p> },
        { id: "keep", title: "How long we keep it", body: <p>Order and payment records are kept as long as tax law requires. Everything else is deleted when you delete your account.</p> },
        { id: "rights", title: "Your choices", body: <p>You can see and correct your details, and delete your account from the BhojanGo app (Account → Delete account). In India this follows the Digital Personal Data Protection Act, 2023; in the US, applicable state privacy laws.</p> },
        { id: "cookies", title: "Cookies and storage", body: <p>We store your sign-in and your bag in your browser so they survive a refresh. We don&apos;t use advertising trackers.</p> },
        { id: "contact", title: "Contact", body: <p>privacy@bhojango.com</p> },
      ]}
    />
  );
}
