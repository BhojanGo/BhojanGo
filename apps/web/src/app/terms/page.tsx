import Link from "next/link";

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-16">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Terms of Service</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: April 2026</p>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 prose prose-sm prose-gray max-w-none">
          <h2>1. Acceptance of Terms</h2>
          <p>By using BhojanGo, you agree to these Terms of Service. If you do not agree, do not use our platform.</p>

          <h2>2. Service Description</h2>
          <p>BhojanGo is a food delivery platform connecting customers with restaurants and delivery partners. We facilitate ordering, payment processing, and delivery coordination.</p>

          <h2>3. User Accounts</h2>
          <p>You must provide accurate information when creating an account. You are responsible for maintaining the security of your account credentials. You must be at least 18 years old to use our services.</p>

          <h2>4. Orders & Payments</h2>
          <p>All prices are displayed in the local currency (USD or INR). Prices include applicable taxes. Delivery fees and minimum order amounts vary by restaurant. Payment is processed at the time of order placement.</p>

          <h2>5. Cancellations & Refunds</h2>
          <p>Orders can be cancelled while in &quot;pending&quot; or &quot;confirmed&quot; status. Once preparation begins, cancellation may not be possible. Refunds are processed within 5-7 business days.</p>

          <h2>6. Restaurant Partners</h2>
          <p>Restaurants are independent businesses. BhojanGo is not responsible for food quality, preparation, or allergen information. Restaurant listings are subject to approval and compliance with our quality standards.</p>

          <h2>7. Delivery</h2>
          <p>Estimated delivery times are approximate. Actual delivery times may vary based on distance, traffic, and restaurant preparation time. BhojanGo is not liable for delays beyond our control.</p>

          <h2>8. Limitation of Liability</h2>
          <p>BhojanGo&apos;s liability is limited to the amount paid for the specific order in question. We are not liable for indirect, incidental, or consequential damages.</p>

          <h2>9. Governing Law</h2>
          <p>These terms are governed by the laws of the jurisdiction where the order is placed (United States or India, as applicable).</p>

          <h2>10. Contact</h2>
          <p>For questions about these terms, contact <a href="mailto:legal@bhojango.com">legal@bhojango.com</a>.</p>
        </div>
        <p className="mt-6 text-center text-sm text-gray-400">
          <Link href="/" className="text-emerald-500 hover:underline">Back to home</Link>
        </p>
      </div>
    </div>
  );
}
