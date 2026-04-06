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
      <section className="bg-brand-500 py-16 text-center text-white">
        <h2 className="text-3xl font-bold">Ready to order?</h2>
        <p className="mt-2 text-brand-100">Thousands of restaurants. One app.</p>
        <div className="mt-6 flex items-center justify-center gap-4">
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
      </section>
    </main>
  );
}
