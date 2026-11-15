// Phones upright, tablets sideways (lib/formFactor.ts): the orientation lock the
// app sets at start, and the one breakpoint hook every screen reads.
import { useEffect } from "react";
import { Dimensions, Platform, useWindowDimensions } from "react-native";

import { isNarrow, lockFor } from "./formFactor";

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
 * Locks the screen once at start: portrait on a phone, landscape on a tablet
 * (app.json's orientation is "default", so the manifest allows both and this
 * decides). Decided from the whole screen, so it never flips mid-shift.
 */
export function useOrientationLock() {
  useEffect(() => {
    if (Platform.OS === "web") return;
    const ScreenOrientation = screenOrientation();
    if (!ScreenOrientation) return;
    const lock = lockFor(Dimensions.get("screen")) === "portrait"
      ? ScreenOrientation.OrientationLock.PORTRAIT_UP
      : ScreenOrientation.OrientationLock.LANDSCAPE;
    // A failed lock leaves the device free to rotate: every screen still lays out by width.
    ScreenOrientation.lockAsync(lock).catch(() => undefined);
  }, []);
}

/**
 * The layout: `narrow` (under 600 dp wide) is the phone layout (one column, list
 * then detail, a bottom tab bar); otherwise the tablet board.
 */
export function useLayout() {
  const { width, height } = useWindowDimensions();
  return { width, height, narrow: isNarrow({ width, height }) };
}
