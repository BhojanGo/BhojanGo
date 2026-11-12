// The orders board, shared by every screen: polled every 4 s; while a new
// order waits, the tablet rings (loud, looping) and vibrates until it's
// accepted, rejected or times out.
import { createAudioPlayer, setAudioModeAsync, type AudioPlayer } from "expo-audio";
import { useEffect } from "react";
import { Vibration } from "react-native";
import { create } from "zustand";

import { getBoard, getToday, type Order, type Today } from "./data";

export const NEW = ["placed"];
export const COOKING = ["accepted", "preparing", "almost_ready"];
export const READY = ["ready"];

interface BoardStore {
  orders: Order[];
  today: Today | null;
  error: string | null;
  muted: boolean;
  refresh: (kitchenId: string) => Promise<void>;
  setToday: (t: Today) => void;
  mute: (on: boolean) => void;
}

export const useBoard = create<BoardStore>()((set) => ({
  orders: [],
  today: null,
  error: null,
  muted: false,
  refresh: async (id) => {
    try {
      const [orders, today] = await Promise.all([getBoard(id), getToday(id)]);
      set({ orders, today, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
  setToday: (today) => set({ today }),
  mute: (muted) => set({ muted }),
}));

let player: AudioPlayer | null = null;

function ring(on: boolean) {
  if (on) {
    if (!player) {
      void setAudioModeAsync({ playsInSilentMode: true, shouldPlayInBackground: true }).catch(() => undefined);
      player = createAudioPlayer(require("../assets/new-order.wav"));
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

/** Poll the board for this kitchen and ring while a new order waits. */
export function useBoardLoop(kitchenId: string | undefined) {
  const refresh = useBoard((s) => s.refresh);
  const waiting = useBoard((s) => s.orders.some((o) => NEW.includes(o.status)));
  const muted = useBoard((s) => s.muted);
  useEffect(() => {
    if (!kitchenId) return;
    void refresh(kitchenId);
    const t = setInterval(() => void refresh(kitchenId), 4000);
    return () => clearInterval(t);
  }, [kitchenId, refresh]);
  useEffect(() => {
    ring(waiting && !muted);
    return () => ring(false);
  }, [waiting, muted]);
}
