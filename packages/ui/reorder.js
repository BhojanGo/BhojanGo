// "Order again" (R27): what POST /orders/{id}/reorder gives, as bag lines and the sentences that say
// what changed. Shared by the website and the customer app; no DOM, no React Native.
//
// R26: "Order again" on a delivered order failed with "We couldn't add this order to your bag".
// The available items go back in the bag with the same options, add-ons and quantities; an item sold
// out or gone, and an option no longer offered, are named ("Butter Croissant is sold out", "Oat is no
// longer offered for Latte") and the rest is still added.

const PROBLEMS = ["sold_out", "removed", "unavailable", "option_gone"];

/**
 * {restaurant, lines, notes}: `lines` for the bag ({menuItemId, name, unitPrice, quantity, picks, summary}),
 * `notes` as message keys under `prefix` with their values ({key, values}). An older API (no `problems`)
 * names what it left out in `unavailable`.
 */
function reorderToBag(r, prefix = "account.receipt.reorder") {
  const lines = [];
  for (const i of r.items || []) {
    if (i.available === false) continue;
    const quantity = Math.min(50, Math.max(1, Math.round(Number(i.quantity) || 1)));
    const options = Array.isArray(i.options) ? i.options : [];
    lines.push({
      menuItemId: String(i.menu_item_id), name: i.name, unitPrice: Number(i.price) || 0, quantity,
      picks: options.map((o) => ({ group: String(o.group), option: String(o.option) })),
      summary: options.map((o) => o.name || o.option).join(", "),
    });
  }
  const notes = [];
  const named = new Set();
  for (const p of r.problems || []) {
    const reason = PROBLEMS.includes(p.reason) ? p.reason : "unavailable";
    if (reason !== "option_gone") named.add(p.item);
    notes.push({ key: `${prefix}.${reason}`, values: reason === "option_gone" ? { item: p.item, option: p.option || "" } : { item: p.item } });
  }
  const left = [...(r.unavailable || []), ...(r.items || []).filter((i) => i.available === false).map((i) => i.name)];
  for (const item of left) {
    if (named.has(item)) continue;
    named.add(item);
    notes.push({ key: `${prefix}.unavailable`, values: { item } });
  }
  return { restaurant: r.restaurant, lines, notes };
}

module.exports = { reorderToBag, PROBLEMS };
