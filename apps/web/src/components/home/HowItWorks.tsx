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
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">How BhojanGo works</h2>
          <p className="mt-2 text-gray-500 dark:text-gray-400">Order in 4 simple steps</p>
        </div>

        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <div key={i} className="relative text-center">
              {i < steps.length - 1 && (
                <div className="absolute right-0 top-8 hidden h-0.5 w-full translate-x-1/2 bg-gray-200 dark:bg-gray-700 lg:block" aria-hidden="true" />
              )}
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-brand-50 text-3xl dark:bg-brand-900">
                {step.icon}
              </div>
              <div className="mt-4 font-medium text-brand-500">{String(i + 1).padStart(2, "0")}</div>
              <h3 className="mt-1 font-semibold text-gray-900 dark:text-white">{step.title}</h3>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
