"use client";
// Back from the bank (Stripe's return_url): Stripe adds payment_intent and
// redirect_status; the order's payment status (set by Stripe's webhook) decides.
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useBag, useHydrated, useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";
import { waitForPayment, type PayStatus } from "../pay";

export function PaymentReturn() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const clear = useBag((s) => s.clear);
  const orderId = params.get("order");
  const redirect = params.get("redirect_status"); // succeeded | processing | failed
  const [status, setStatus] = useState<PayStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (hydrated && !user) router.replace(`/signin?next=${encodeURIComponent(`/checkout/return?${params.toString()}`)}`);
  }, [hydrated, user, router, params]);

  useEffect(() => {
    if (!hydrated || !user || !orderId) return;
    let live = true;
    // A redirect that failed at the bank still waits briefly: the webhook is the truth.
    waitForPayment(orderId, redirect === "failed" ? 5000 : 30000)
      .then((s) => {
        if (!live) return;
        if (s.payment_status === "succeeded") {
          clear();
          router.replace(`/orders/${orderId}/track`);
          return;
        }
        setStatus(s);
      })
      .catch(() => live && setError(true));
    return () => {
      live = false;
    };
  }, [hydrated, user, orderId, redirect, clear, router]);

  const failed = !!orderId && (error || (status != null && status.payment_status !== "succeeded" && (status.payment_status === "failed" || redirect === "failed")));
  const slow = status != null && !failed;
  const title = !orderId || failed ? t("checkout.return_failed_title") : slow ? t("checkout.return_slow_title") : t("checkout.return_title");
  const body = !orderId
    ? t("checkout.return_missing")
    : error
      ? t("common.error")
      : failed
        ? status?.failure_reason
          ? t("checkout.payment_failed_reason", { reason: status.failure_reason })
          : t("checkout.payment_failed")
        : slow
          ? t("checkout.payment_slow")
          : t("checkout.return_body");

  return (
    <div className="container-page flex justify-center py-16 md:py-24">
      <div className="w-full max-w-md rounded-[28px] border border-[#E3E8E9] bg-white p-6 text-center md:p-8">
        {!failed && !slow && orderId ? (
          <div aria-hidden="true" className="mx-auto mb-5 h-10 w-10 animate-spin rounded-full border-4 border-[#CFE3E5] border-t-[#0B5D66]" />
        ) : null}
        <h1 className="text-h2">{title}</h1>
        <p role={failed ? "alert" : "status"} className="mt-2 text-body text-muted">{body}</p>
        {(failed || !orderId) && (
          <Link href="/checkout" className="mt-6 inline-flex h-12 items-center rounded-full bg-[#0B5D66] px-6 font-bold text-white hover:text-white">
            {t("checkout.back_to_checkout")}
          </Link>
        )}
        {slow && orderId && (
          <Link href={`/orders/${orderId}/track`} className="mt-6 inline-flex h-12 items-center rounded-full bg-[#0B5D66] px-6 font-bold text-white hover:text-white">
            {t("checkout.view_order")}
          </Link>
        )}
      </div>
    </div>
  );
}
