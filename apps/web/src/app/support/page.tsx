import Link from "next/link";

export default function SupportPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-16">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Support</h1>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Contact Us</h2>
            <p className="text-gray-600 text-sm">
              Need help with your order or account? Our support team is available 24/7.
            </p>
            <p className="text-sm text-gray-600 mt-2">
              Email: <a href="mailto:support@bhojango.com" className="text-emerald-600 hover:underline">support@bhojango.com</a>
            </p>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">FAQs</h2>
            <div className="space-y-4">
              {[
                { q: "How do I track my order?", a: "Go to My Orders and click on the active order to see real-time tracking." },
                { q: "How do I cancel an order?", a: "You can cancel from the order detail page while the order is still in 'pending' or 'confirmed' status." },
                { q: "How do refunds work?", a: "Refunds are processed automatically within 5-7 business days to your original payment method." },
                { q: "How do I become a restaurant partner?", a: "Sign up as a Restaurant Owner from the registration page. Once you submit your restaurant details, our team will review and approve it." },
              ].map((faq, i) => (
                <details key={i} className="border border-gray-200 rounded-lg">
                  <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-gray-900 hover:bg-gray-50">{faq.q}</summary>
                  <p className="px-4 pb-3 text-sm text-gray-600">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-6 text-center text-sm text-gray-400">
          <Link href="/" className="text-emerald-500 hover:underline">Back to home</Link>
        </p>
      </div>
    </div>
  );
}
