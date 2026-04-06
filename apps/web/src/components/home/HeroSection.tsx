"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Input } from "@bhojango/ui";

export function HeroSection() {
  const router = useRouter();
  const [city, setCity] = useState("");

  const handleSearch = () => {
    if (city.trim()) {
      router.push(`/restaurants?city=${encodeURIComponent(city.trim())}`);
    } else {
      router.push("/restaurants");
    }
  };

  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-brand-500 to-brand-700 px-4 py-24 text-white">
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-10" aria-hidden="true">
        <div className="absolute -left-10 -top-10 h-96 w-96 rounded-full bg-white" />
        <div className="absolute -bottom-10 -right-10 h-64 w-64 rounded-full bg-white" />
      </div>

      <div className="relative mx-auto max-w-4xl text-center">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl">
          Delicious food,{" "}
          <span className="text-brand-100">delivered fast</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-xl text-brand-100">
          Order from hundreds of restaurants near you. Fresh meals delivered in 30 minutes or less.
        </p>

        <div className="mx-auto mt-10 flex max-w-lg flex-col gap-3 sm:flex-row">
          <Input
            placeholder="Enter your city (e.g. New York, Mumbai)"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1 h-12 text-gray-900"
            aria-label="City for food search"
          />
          <Button onClick={handleSearch} size="lg" variant="secondary" className="shrink-0">
            Find Food
          </Button>
        </div>

        <div className="mt-8 flex items-center justify-center gap-8 text-sm text-brand-100">
          <span>🍕 1000+ Restaurants</span>
          <span>🛵 Fast Delivery</span>
          <span>⭐ Top Rated</span>
        </div>
      </div>
    </section>
  );
}
