"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

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
    <section className="relative overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-brand-500 px-4 py-28 text-white">
      {/* Background decoration */}
      <div className="absolute inset-0 opacity-10" aria-hidden="true">
        <div className="absolute -left-20 -top-20 h-[500px] w-[500px] rounded-full bg-accent-400" />
        <div className="absolute -bottom-20 -right-20 h-80 w-80 rounded-full bg-white" />
        <div className="absolute left-1/2 top-1/3 h-40 w-40 rounded-full bg-accent-300" />
      </div>

      <div className="relative mx-auto max-w-4xl text-center">
        <span className="inline-block rounded-full bg-accent-500/20 px-4 py-1.5 text-sm font-medium text-accent-200 backdrop-blur-sm">
          Now delivering in 20+ cities
        </span>

        <h1 className="mt-6 text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
          Delicious food,{" "}
          <span className="text-accent-300">delivered fast</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-brand-100">
          Order from hundreds of restaurants near you. Fresh meals delivered in 30 minutes or less.
        </p>

        <div className="mx-auto mt-10 flex max-w-xl flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <svg className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <input
              type="text"
              placeholder="Enter your city (e.g. New York, Mumbai)"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="h-12 w-full rounded-xl border-0 bg-white pl-10 pr-4 text-gray-900 shadow-lg placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-accent-400"
              aria-label="City for food search"
            />
          </div>
          <button
            onClick={handleSearch}
            className="h-12 shrink-0 rounded-xl bg-accent-500 px-8 font-semibold text-white shadow-lg transition hover:bg-accent-600 hover:shadow-xl active:scale-[0.98]"
          >
            Find Food
          </button>
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-6 text-sm font-medium text-brand-100">
          <span className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10">🍕</span>
            1000+ Restaurants
          </span>
          <span className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10">🛵</span>
            Fast Delivery
          </span>
          <span className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10">⭐</span>
            Top Rated
          </span>
        </div>
      </div>
    </section>
  );
}
