// Phones upright, tablets either way (lib/formFactor.ts): the orientation lock the
// app sets at start, and the one breakpoint hook every screen reads.
import { useEffect } from "react";
import { Dimensions, Platform, useWindowDimensions } from "react-native";

import { isNarrow, isPortrait, lockFor } from "./formFactor";

type ScreenOrientationModule = typeof import("expo-screen-orientation");

/** The native module, or null on an APK built before it was added (that build's manifest still says landscape). */
function screenOrientation(): ScreenOrientationModule | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require("expo-screen-orientation") as ScreenOrientationModule;
  } catch {
    return null;
  }
}

/**
 * Sets the orientation once at start: a phone locks upright; a tablet turns freely
 * (R27: portrait or landscape, every screen lays out for both). app.json's orientation is
 * "default", so the manifest allows both and this decides, from the whole screen.
 */
export function useOrientationLock() {
  useEffect(() => {
    if (Platform.OS === "web") return;
    const ScreenOrientation = screenOrientation();
    if (!ScreenOrientation) return;
    const lock = lockFor(Dimensions.get("screen")) === "portrait"
      ? ScreenOrientation.OrientationLock.PORTRAIT_UP
      : ScreenOrientation.OrientationLock.DEFAULT;
    // A failed lock leaves the device free to rotate: every screen still lays out by width.
    ScreenOrientation.lockAsync(lock).catch(() => undefined);
  }, []);
}

/**
 * The layout: `narrow` (under 600 dp wide) is the phone layout (one column, list
 * then detail, a bottom tab bar); otherwise the tablet board. `portrait` (taller than
 * wide): a tablet upright, where the board's columns become tabs and panels stack.
 */
export function useLayout() {
  const { width, height } = useWindowDimensions();
  return { width, height, narrow: isNarrow({ width, height }), portrait: isPortrait({ width, height }) };
}
