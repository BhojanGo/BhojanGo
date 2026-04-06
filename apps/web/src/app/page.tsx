import Link from "next/link";

import { Button } from "@bhojango/ui";

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
      <section className="bg-gradient-to-r from-brand-600 to-brand-500 py-20 text-center text-white">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="text-3xl font-bold sm:text-4xl">Ready to order?</h2>
          <p className="mt-3 text-lg text-brand-100">Thousands of restaurants. One app. Free delivery on your first order.</p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link href="/restaurants">
              <Button variant="secondary" size="lg">
                Browse Restaurants
              </Button>
            </Link>
            <Link href="/signup">
              <Button variant="outline" size="lg" className="border-white text-white hover:bg-white/10">
                Sign Up Free
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
