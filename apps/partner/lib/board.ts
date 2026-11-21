// The orders board, shared by every screen. While a new order waits, the tablet rings (loud,
// looping) and vibrates until it's accepted, rejected or times out.
//
// R27 (the R26 stall: the board silently stopped updating after ~75 min):
// - one refresh at a time; a refresh still running after STUCK_AFTER_MS is treated as lost
//   (lib/liveness.ts), and every request under it gives up on its own (GETs after 8 s, the
//   token refresh after 15 s: mobile-core refresh.ts), so a hung request can't freeze the board;
// - a watchdog: the time of the last good update. No good poll (and no socket message) for 15 s:
//   `offline`, and every Kitchen screen shows the red "Not receiving orders" banner with an alarm
//   (lib/offline.tsx) until updates come back;
// - realtime first: the kitchen's socket (/ws/kitchen/{id}) brings each order change and answers a
//   ping every 10 s (the tablet's heartbeat on the server: a kitchen whose tablet is silent for
//   60 s is paused for customers); polling stays as the fallback, every 4 s, 12 s while the socket is up;
// - the server's clock (each poll's Date header): accept timers count down to the real deadline.
import { liveSocket } from "@bhojango/mobile-core";
import { createAudioPlayer, setAudioModeAsync, type AudioPlayer } from "expo-audio";
import { useEffect } from "react";
import { AppState, Vibration } from "react-native";
import { create } from "zustand";

import { getBoardTimed, getToday, type Order, type Today } from "./data";
import { isOffline, mayStart, pollDue, pollEvery, SOCKET_HEARTBEAT_MS, type Link } from "./liveness";

export const NEW = ["placed"];
export const COOKING = ["accepted", "preparing", "almost_ready"];
export const READY = ["ready"];

interface BoardStore {
  orders: Order[];
  today: Today | null;
  error: string | null;
  /** What the last refresh threw (LoadError / loadErrorText word it); null after a good one. */
  failure: unknown;
  muted: boolean;
  /** The server's clock minus this tablet's (ms), from the last poll: accept timers use server time. */
  skew: number;
  /** When the board last heard from the server (liveness.ts). */
  link: Link;
  /** No good poll and no socket message for 15 s: the tablet isn't receiving orders. */
  offline: boolean;
  refresh: (kitchenId: string) => Promise<void>;
  /** Something came in over the realtime socket (an event or a pong). */
  heard: () => void;
  setToday: (t: Today) => void;
  mute: (on: boolean) => void;
}

// The refresh running now (one at a time) and the last one whose answer was used.
let running: { since: number; seq: number; done: Promise<void> } | null = null;
let seq = 0;
let applied = 0;
// Asked again while one was running (an accept, a socket event): one more right after it, shared.
let again: { after: number; done: Promise<void> } | null = null;

export const useBoard = create<BoardStore>()((set, get) => ({
  orders: [],
  today: null,
  error: null,
  failure: null,
  muted: false,
  skew: 0,
  link: { since: Date.now(), lastPoll: null, lastSocket: null },
  offline: false,
  refresh: (id) => {
    const now = Date.now();
    if (running && !mayStart(running.since, now)) {
      const after = running.seq;
      if (again?.after !== after) {
        const next = running.done.then(() => {
          if (again?.after === after) again = null;
          return get().refresh(id);
        });
        again = { after, done: next };
      }
      return again.done;
    }
    const mine = ++seq;
    const done = (async () => {
      try {
        const [board, today] = await Promise.all([getBoardTimed(id), getToday(id)]);
        if (mine < applied) return; // a newer refresh already answered
        applied = mine;
        set((s) => ({
          orders: board.items, today, error: null, failure: null, skew: board.skew ?? s.skew,
          link: { ...s.link, lastPoll: Date.now() }, offline: false,
        }));
      } catch (e) {
        if (mine < applied) return;
        set({ error: (e as Error).message, failure: e });
      } finally {
        if (running?.seq === mine) running = null;
      }
    })();
    running = { since: now, seq: mine, done };
    return done;
  },
  heard: () => set((s) => ({ link: { ...s.link, lastSocket: Date.now() }, offline: false })),
  setToday: (today) => set({ today }),
  mute: (muted) => set({ muted }),
}));

/** A socket message's type ("order_changed", "connected", "ping"); null for "pong" and anything else. */
function messageType(data: unknown): string | null {
  if (typeof data !== "string" || !data.startsWith("{")) return null;
  try {
    return (JSON.parse(data) as { type?: string }).type ?? null;
  } catch {
    return null;
  }
}

/** The watchdog's look (every second): is the tablet still hearing from the server? */
function watch(now: number) {
  const s = useBoard.getState();
  const off = isOffline(s.link, now);
  if (off !== s.offline) useBoard.setState({ offline: off });
}

let player: AudioPlayer | null = null;

function ring(on: boolean) {
  if (on) {
    if (!player) {
      // Foreground only (R20): the board polls while the app is open, so a new order can only ring
      // here then; in the background the order's push notification (with its sound) is the alert.
      // No background audio, so no iOS UIBackgroundModes "audio" (app.json: enableBackgroundPlayback false).
      void setAudioModeAsync({ playsInSilentMode: true, shouldPlayInBackground: false }).catch(() => undefined);
      player = createAudioPlayer(require("../assets/new_order.wav"));
      player.loop = true;
      player.volume = 1;
    }
    if (!player.playing) player.play();
    Vibration.vibrate([0, 600, 400], true);
  } else {
    player?.pause();
    Vibration.cancel();
  }
}

let alarmPlayer: AudioPlayer | null = null;
const ALARM_EVERY_MS = 20000;

/** R27: the "Not receiving orders" alarm: a short two-tone sound now and every 20 s while offline. */
function alarm(on: boolean): (() => void) | undefined {
  if (!on) return undefined;
  const play = () => {
    try {
      if (!alarmPlayer) {
        void setAudioModeAsync({ playsInSilentMode: true, shouldPlayInBackground: false }).catch(() => undefined);
        alarmPlayer = createAudioPlayer(require("../assets/offline-alarm.wav"));
        alarmPlayer.volume = 1;
      }
      void alarmPlayer.seekTo(0).catch(() => undefined);
      alarmPlayer.play();
    } catch {
      // no sound (an emulator without audio): the banner still shows
    }
  };
  play();
  const t = setInterval(play, ALARM_EVERY_MS);
  return () => {
    clearInterval(t);
    alarmPlayer?.pause();
  };
}

/**
 * Keep the board of this kitchen fresh (every Kitchen screen: the root layout runs it), ring while
 * a new order waits, and sound the alarm while the tablet isn't receiving orders.
 */
export function useBoardLoop(kitchenId: string | undefined) {
  const refresh = useBoard((s) => s.refresh);
  const waiting = useBoard((s) => s.orders.some((o) => NEW.includes(o.status)));
  const muted = useBoard((s) => s.muted);
  const offline = useBoard((s) => s.offline && !!kitchenId);
  useEffect(() => {
    if (!kitchenId) {
      useBoard.setState({ offline: false });
      return;
    }
    useBoard.setState((s) => ({ link: { ...s.link, since: Date.now() }, offline: false }));
    let lastStart: number | null = null;
    const tick = () => {
      const now = Date.now();
      watch(now);
      if (pollDue(lastStart, now, pollEvery(useBoard.getState().link, now)) && mayStart(running?.since ?? null, now)) {
        lastStart = now;
        void refresh(kitchenId);
      }
    };
    tick();
    const t = setInterval(tick, 1000);
    // Realtime first (R27): the kitchen's socket brings each order change at once (the board
    // refreshes on it), and its pong to the 10 s ping is the tablet's heartbeat on the server too.
    const stopSocket = liveSocket(`/ws/kitchen/${kitchenId}`, (e) => {
      useBoard.getState().heard();
      const kind = messageType(e.data);
      if (kind === "order_changed" || kind === "connected") void refresh(kitchenId);
    }, { heartbeatMs: SOCKET_HEARTBEAT_MS });
    // Back in front (the screen woke, another app closed): refresh at once.
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        lastStart = null;
        tick();
      }
    });
    return () => {
      clearInterval(t);
      sub.remove();
      stopSocket();
    };
  }, [kitchenId, refresh]);
  useEffect(() => {
    ring(waiting && !muted);
    return () => ring(false);
  }, [waiting, muted]);
  useEffect(() => alarm(offline), [offline]);
}
