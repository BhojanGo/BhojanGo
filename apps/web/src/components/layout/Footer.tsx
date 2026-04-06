import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
      <div className="mx-auto max-w-7xl px-4 py-12">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div>
            <Link href="/" className="text-xl font-bold text-brand-500">
              BhojanGo
            </Link>
            <p className="mt-3 text-sm text-gray-500">
              Delicious food, delivered fast. Available in USA and India.
            </p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Explore</h4>
            <ul className="mt-3 space-y-2 text-sm text-gray-500">
              <li><Link href="/restaurants" className="hover:text-brand-500 transition">Restaurants</Link></li>
              <li><Link href="/cart" className="hover:text-brand-500 transition">Cart</Link></li>
              <li><Link href="/orders" className="hover:text-brand-500 transition">My Orders</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Account</h4>
            <ul className="mt-3 space-y-2 text-sm text-gray-500">
              <li><Link href="/login" className="hover:text-brand-500 transition">Login</Link></li>
              <li><Link href="/signup" className="hover:text-brand-500 transition">Sign Up</Link></li>
              <li><Link href="/profile" className="hover:text-brand-500 transition">Profile</Link></li>
              <li><Link href="/wallet" className="hover:text-brand-500 transition">Wallet</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Support</h4>
            <ul className="mt-3 space-y-2 text-sm text-gray-500">
              <li><span className="cursor-default">Help Center</span></li>
              <li><span className="cursor-default">Privacy Policy</span></li>
              <li><span className="cursor-default">Terms of Service</span></li>
            </ul>
          </div>
        </div>

        <div className="mt-10 border-t border-gray-200 pt-6 text-center text-xs text-gray-400 dark:border-gray-800">
          &copy; {new Date().getFullYear()} BhojanGo Inc. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
