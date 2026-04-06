import Link from "next/link";

import { FeaturedRestaurants } from "@/components/home/FeaturedRestaurants";
import { HeroSection } from "@/components/home/HeroSection";
import { HowItWorks } from "@/components/home/HowItWorks";

export default function HomePage() {
  return (
    <main>
      <HeroSection />
      <FeaturedRestaurants />
      <HowItWorks />

      {/* CTA */}
      <section className="bg-gradient-to-r from-emerald-700 to-teal-600 py-20 text-center text-white">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="text-3xl font-bold sm:text-4xl">Ready to order?</h2>
          <p className="mt-3 text-lg text-emerald-100/90">Thousands of restaurants. One app. Free delivery on your first order.</p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/restaurants"
              className="inline-flex h-12 items-center rounded-xl bg-white px-8 font-semibold text-emerald-700 shadow-lg transition hover:bg-gray-100 hover:shadow-xl"
            >
              Browse Restaurants
            </Link>
            <Link
              href="/signup"
              className="inline-flex h-12 items-center rounded-xl border-2 border-white/50 px-8 font-semibold text-white transition hover:bg-white/10"
            >
              Sign Up Free
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
