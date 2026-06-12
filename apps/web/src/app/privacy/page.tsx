import Link from "next/link";

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-16">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Privacy Policy</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: April 2026</p>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 prose prose-sm prose-gray max-w-none">
          <h2>1. Information We Collect</h2>
          <p>We collect information you provide directly, including your name, email address, phone number, delivery addresses, and payment information when you create an account or place an order.</p>

          <h2>2. How We Use Your Information</h2>
          <p>We use your information to process orders, facilitate deliveries, communicate updates, improve our services, and ensure platform safety.</p>

          <h2>3. Information Sharing</h2>
          <p>We share your information with restaurant partners to fulfill orders, delivery drivers for deliveries, and payment processors to handle transactions. We do not sell your personal data.</p>

          <h2>4. Data Security</h2>
          <p>We implement industry-standard security measures including encryption in transit (TLS), encrypted storage, and access controls to protect your personal information.</p>

          <h2>5. Your Rights</h2>
          <p>You have the right to access, correct, or delete your personal data. You can exercise these rights through your account settings or by contacting support@bhojango.com.</p>
          <p>Under GDPR and India PDPA, you can request a complete deletion of your data. We will anonymize your records within 30 days while retaining necessary transactional data.</p>

          <h2>6. Cookies</h2>
          <p>We use essential cookies for authentication and session management. We do not use third-party tracking cookies without your consent.</p>

          <h2>7. Contact</h2>
          <p>For privacy-related inquiries, contact us at <a href="mailto:privacy@bhojango.com">privacy@bhojango.com</a>.</p>
        </div>
        <p className="mt-6 text-center text-sm text-gray-400">
          <Link href="/" className="text-emerald-500 hover:underline">Back to home</Link>
        </p>
      </div>
    </div>
  );
}
