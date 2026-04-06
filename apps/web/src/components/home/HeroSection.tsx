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
    <section className="relative overflow-hidden bg-gradient-to-br from-emerald-800 via-emerald-700 to-teal-600 px-4 py-28 text-white">
      {/* Background decoration */}
      <div className="absolute inset-0" aria-hidden="true">
        <div className="absolute -left-20 -top-20 h-[500px] w-[500px] rounded-full bg-emerald-500/10" />
        <div className="absolute -bottom-20 -right-20 h-80 w-80 rounded-full bg-teal-400/10" />
        <div className="absolute left-1/2 top-1/3 h-40 w-40 rounded-full bg-amber-400/10" />
      </div>

      <div className="relative mx-auto max-w-4xl text-center">
        <span className="inline-block rounded-full border border-emerald-400/30 bg-emerald-500/20 px-4 py-1.5 text-sm font-medium text-emerald-100 backdrop-blur-sm">
          Now delivering in 20+ cities
        </span>

        <h1 className="mt-6 text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
          Delicious food,{" "}
          <span className="text-amber-300">delivered fast</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-emerald-100/90">
          Order from hundreds of restaurants near you. Fresh meals delivered in 30 minutes or less.
        </p>

        <div className="mx-auto mt-10 flex max-w-xl flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <svg className="absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <input
              type="text"
              placeholder="Enter your city (e.g. New York, Mumbai)"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="h-13 w-full rounded-xl border-0 bg-white pl-11 pr-4 text-gray-900 shadow-xl placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-400"
              aria-label="City for food search"
            />
          </div>
          <button
            onClick={handleSearch}
            className="h-13 shrink-0 rounded-xl bg-amber-500 px-8 font-bold text-white shadow-xl transition hover:bg-amber-600 hover:shadow-2xl active:scale-[0.97]"
          >
            Find Food
          </button>
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-8 text-sm font-medium text-emerald-100/80">
          <span className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-lg backdrop-blur-sm">🍕</span>
            1000+ Restaurants
          </span>
          <span className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-lg backdrop-blur-sm">🛵</span>
            Fast Delivery
          </span>
          <span className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-lg backdrop-blur-sm">⭐</span>
            Top Rated
          </span>
        </div>
      </div>
    </section>
  );
}
