import Link from "next/link";

export default function HelpCenterPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-16">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Help Center</h1>
        <div className="grid gap-4 md:grid-cols-2">
          {[
            { title: "Getting Started", desc: "Learn how to create an account, browse restaurants, and place your first order.", icon: "🚀" },
            { title: "Orders & Delivery", desc: "Track orders, manage delivery preferences, and understand delivery times.", icon: "📦" },
            { title: "Payments & Wallet", desc: "Payment methods, wallet top-ups, refunds, and billing questions.", icon: "💳" },
            { title: "Account Settings", desc: "Update profile, change password, manage addresses, and notification preferences.", icon: "⚙️" },
            { title: "Restaurant Partners", desc: "How to list your restaurant, manage menus, and handle orders.", icon: "🍽️" },
            { title: "Driver Support", desc: "Delivery partner onboarding, earnings, and trip-related help.", icon: "🚗" },
          ].map((section, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 p-6 hover:shadow-md transition">
              <div className="text-2xl mb-3">{section.icon}</div>
              <h3 className="font-semibold text-gray-900 mb-1">{section.title}</h3>
              <p className="text-sm text-gray-500">{section.desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-8 bg-white rounded-xl border border-gray-100 p-6 text-center">
          <p className="text-gray-600 text-sm mb-3">Can&apos;t find what you&apos;re looking for?</p>
          <Link href="/support" className="text-emerald-600 font-semibold text-sm hover:underline">
            Contact Support
          </Link>
        </div>
      </div>
    </div>
  );
}
