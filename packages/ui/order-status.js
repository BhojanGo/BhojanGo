// R44: an order's status as the tracking screens show it (website and customer app). An order only moves forward, so
// of the status the API returned and the one the live socket last said, the screen shows the later one.
//
// R44 bug (customer app, round 44's run): realtime sends "eta_update" with the status it computed the ETA for; one for
// "preparing" arrived after "ready", and the socket's status always won over the order's, so a ready pickup order showed
// "Ready in about 20 min" and "Cooking" next to its pickup code until the next socket message.

/** The order of an order's life; cancelled (and pending_payment's end) are handled separately. */
export const STATUS_STEPS = ["pending_payment", "placed", "accepted", "preparing", "almost_ready", "ready", "picked_up", "delivered"];

/** Where a status is in the order's life (-1 if unknown). */
export function statusStep(status) {
  return STATUS_STEPS.indexOf(status ?? "");
}

/**
 * The status to show: cancelled wins; otherwise the later of the order's (API) and the live one. Unknown live values
 * never replace a known order status.
 */
export function shownStatus(orderStatus, liveStatus) {
  if (orderStatus === "cancelled" || liveStatus === "cancelled") return "cancelled";
  if (!liveStatus) return orderStatus ?? "placed";
  if (!orderStatus) return liveStatus;
  return statusStep(liveStatus) > statusStep(orderStatus) ? liveStatus : orderStatus;
}

/** The live status after a socket message: never backwards (a late message for an earlier step is ignored). */
export function nextLiveStatus(current, incoming) {
  if (!incoming) return current ?? null;
  if (!current || incoming === "cancelled") return incoming;
  if (current === "cancelled") return current;
  return statusStep(incoming) >= statusStep(current) ? incoming : current;
}
