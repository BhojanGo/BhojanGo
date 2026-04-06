const steps = [
  { icon: "📍", title: "Choose your location", description: "Enter your delivery address to see restaurants nearby." },
  { icon: "🍽️", title: "Pick your favourite", description: "Browse menus, check ratings, and add items to your cart." },
  { icon: "💳", title: "Pay securely", description: "Multiple payment options — card, UPI, or wallet." },
  { icon: "🛵", title: "Track in real time", description: "Follow your driver on the map as your order makes its way to you." },
];

export function HowItWorks() {
  return (
    <section className="bg-white py-20 dark:bg-gray-900">
      <div className="mx-auto max-w-6xl px-4">
        <div className="text-center">
          <span className="inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            How it works
          </span>
          <h2 className="mt-4 text-3xl font-bold text-gray-900 dark:text-white">Order in 4 simple steps</h2>
        </div>

        <div className="mt-14 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <div key={i} className="relative text-center" >
              {i < steps.length - 1 && (
                <div className="absolute right-0 top-8 hidden h-0.5 w-full translate-x-1/2 bg-emerald-200 dark:bg-emerald-800 lg:block" aria-hidden="true" />
              )}
              <div className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-3xl shadow-sm dark:bg-emerald-900/20">
                {step.icon}
                <span className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-amber-500 text-xs font-bold text-white shadow-sm">
                  {i + 1}
                </span>
              </div>
              <h3 className="mt-5 font-semibold text-gray-900 dark:text-white">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-gray-500 dark:text-gray-400">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
