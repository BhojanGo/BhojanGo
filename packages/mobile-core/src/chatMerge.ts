// R35: the live chat's lost-message race. A list fetch (a poll, a status change, a quick
// message) that started before a message was sent can finish after it was added on
// screen (by send() or the socket); replacing the list then dropped that message until
// the next poll (the 1-in-50 "live chat" failure). Messages are never deleted, so a fetch
// is merged: the fetched list, plus anything already on screen that it doesn't have yet.

interface Msg { id: string; at: string }

export function mergeMessages<M extends Msg>(fetched: M[], shown: M[] | undefined): M[] {
  if (!shown?.length) return fetched;
  const have = new Set(fetched.map((m) => m.id));
  const extra = shown.filter((m) => !have.has(m.id));
  if (!extra.length) return fetched;
  return [...fetched, ...extra].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
}

interface ChatLike<M extends Msg & { mine?: boolean }> { open?: boolean; blocked?: boolean; messages: M[] }

/** A fetched conversation applied over the one on screen: merged, except that a closed
 *  conversation replaces it, and after a block only my own messages carry over (R19). */
export function mergeChat<M extends Msg & { mine?: boolean }, C extends ChatLike<M>>(fetched: C, shown: C | null | undefined): C {
  if (!shown || fetched.open === false) return fetched;
  const keep = fetched.blocked ? shown.messages.filter((m) => m.mine) : shown.messages;
  return { ...fetched, messages: mergeMessages(fetched.messages, keep) };
}
