import type { Metadata } from "next";
import { Familjen_Grotesk, Hanken_Grotesk } from "next/font/google";
import Link from "next/link";

import { HeaderActions } from "@/components/HeaderActions";
import { cities, SITE } from "@/lib/server";
import { Logo } from "@bhojango/ui";
import "./globals.css";

// Design system fonts (P16): display for headings and big numbers, text for everything else.
const display = Familjen_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-display" });
const text = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"], variable: "--font-text" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: "BhojanGo — real food, fair prices", template: "%s · BhojanGo" },
  description: "Order from local kitchens with every fee shown before you pay: who gets each rupee or dollar, the kitchen, the rider, tax and us.",
  openGraph: { type: "website", siteName: "BhojanGo" },
  robots: { index: true, follow: true },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const list = await cities();
  return (
    <html lang="en">
      <body className={`${display.variable} ${text.variable} font-sans antialiased bg-porcelain text-kohl`}>
        <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
          <div className="mx-auto flex h-16 max-w-content items-center gap-6 px-5 md:px-8">
            <Link href="/" aria-label="BhojanGo home"><Logo size={30} /></Link>
            <nav aria-label="Cities" className="hidden gap-5 text-sm font-semibold text-muted md:flex">
              {list.map((c) => <Link key={c.slug} href={`/${c.slug}`} className="hover:text-peacock">{c.name}</Link>)}
            </nav>
            <div className="flex-1" />
            <HeaderActions />
          </div>
        </header>
        <main className="min-h-[70vh]">{children}</main>
        <footer className="mt-16 border-t border-line bg-white">
          <div className="mx-auto grid max-w-content gap-8 px-5 py-10 text-sm md:grid-cols-4 md:px-8">
            <div className="space-y-3">
              <Logo size={26} />
              <p className="text-muted">Real food. Fair prices. Every fee shown before you pay.</p>
            </div>
            <div>
              <h2 className="mb-3 font-bold">Order in</h2>
              <ul className="space-y-2 text-muted">
                {list.map((c) => <li key={c.slug}><Link href={`/${c.slug}`} className="hover:text-peacock">Food delivery in {c.name}</Link></li>)}
              </ul>
            </div>
            <div>
              <h2 className="mb-3 font-bold">Help</h2>
              <ul className="space-y-2 text-muted">
                <li><Link href="/help" className="hover:text-peacock">Help centre</Link></li>
                <li><Link href="/orders" className="hover:text-peacock">Your orders</Link></li>
                <li><Link href="/partner" className="hover:text-peacock">Add your kitchen</Link></li>
              </ul>
            </div>
            <div>
              <h2 className="mb-3 font-bold">Legal</h2>
              <ul className="space-y-2 text-muted">
                <li><Link href="/terms" className="hover:text-peacock">Terms</Link></li>
                <li><Link href="/privacy" className="hover:text-peacock">Privacy</Link></li>
              </ul>
            </div>
          </div>
          <p className="border-t border-line py-4 text-center text-xs text-muted">© {new Date().getFullYear()} BhojanGo</p>
        </footer>
      </body>
    </html>
  );
}
