// node --test: R35, a stale chat fetch never drops a message already on screen.
import assert from "node:assert/strict";
import test from "node:test";

import { mergeChat, mergeMessages } from "../src/lib/chatMerge.ts";

const m = (id: string, at: string, text = id) => ({ id, at, text });

test("a fetch that started before a send keeps the sent message", () => {
  const stale = [m("a", "2026-11-24T10:00:00Z")];
  const shown = [m("a", "2026-11-24T10:00:00Z"), m("mine", "2026-11-24T10:00:05Z")];
  assert.deepEqual(mergeMessages(stale, shown).map((x) => x.id), ["a", "mine"]);
});

test("the fetched copy wins (e.g. a quick message in this page's language)", () => {
  const fetched = [m("a", "2026-11-24T10:00:00Z", "Estoy afuera.")];
  const shown = [m("a", "2026-11-24T10:00:00Z", "I'm outside.")];
  assert.equal(mergeMessages(fetched, shown)[0]!.text, "Estoy afuera.");
});

test("in time order, nothing doubled", () => {
  const fetched = [m("b", "2026-11-24T10:00:02Z"), m("c", "2026-11-24T10:00:03Z")];
  const shown = [m("a", "2026-11-24T10:00:01Z"), m("b", "2026-11-24T10:00:02Z")];
  assert.deepEqual(mergeMessages(fetched, shown).map((x) => x.id), ["a", "b", "c"]);
});

test("nothing shown yet: the fetched list as is", () => {
  const fetched = [m("a", "2026-11-24T10:00:00Z")];
  assert.equal(mergeMessages(fetched, undefined), fetched);
  assert.equal(mergeMessages(fetched, []), fetched);
});

const chat = (messages: { id: string; at: string; text: string; mine?: boolean }[], extra: { open?: boolean; blocked?: boolean } = {}) =>
  ({ open: true, blocked: false, ...extra, messages });

test("a closed conversation replaces the one on screen", () => {
  const shown = chat([{ ...m("a", "2026-11-24T10:00:00Z"), mine: true }]);
  assert.deepEqual(mergeChat(chat([], { open: false }), shown).messages, []);
});

test("after a block, only my own messages carry over", () => {
  const shown = chat([{ ...m("theirs", "2026-11-24T10:00:00Z"), mine: false }, { ...m("mine", "2026-11-24T10:00:01Z"), mine: true }]);
  assert.deepEqual(mergeChat(chat([], { blocked: true }), shown).messages.map((x) => x.id), ["mine"]);
});

test("a stale fetch keeps the message just sent", () => {
  const shown = chat([{ ...m("a", "2026-11-24T10:00:00Z"), mine: false }, { ...m("sent", "2026-11-24T10:00:05Z"), mine: true }]);
  const stale = chat([{ ...m("a", "2026-11-24T10:00:00Z"), mine: false }]);
  assert.deepEqual(mergeChat(stale, shown).messages.map((x) => x.id), ["a", "sent"]);
});
