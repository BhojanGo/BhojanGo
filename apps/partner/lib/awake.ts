// R28: the kitchen tablet's screen never sleeps while someone is signed in.
// expo-keep-awake's useKeepAwake let its deactivate reject unhandled when Android's activity was
// already gone (the "ExpoKeepAwake" error toast) and dropped a failed activate silently, so the
// screen could sleep with nothing said. Here: activate while signed in, again each time the app
// comes back to the foreground (a new activity needs it set again), retry a failed activate, and
// never leave a rejection unhandled. If the OS still sleeps the app, R27's heartbeat pause catches it.
import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";
import { useEffect } from "react";
import { AppState } from "react-native";

import { holdAwake, wantAwake } from "./awakeLogic";

const TAG = "kitchen-tablet";

export function useTabletAwake(signedIn: boolean): void {
  useEffect(() => {
    if (!signedIn) {
      deactivateKeepAwake(TAG).catch(() => undefined);
      return;
    }
    let live = true;
    const apply = (app: string | null | undefined) => {
      if (wantAwake(true, app ?? null)) void holdAwake(() => activateKeepAwakeAsync(TAG), () => live && AppState.currentState === "active");
    };
    apply(AppState.currentState);
    const sub = AppState.addEventListener("change", apply);
    return () => {
      live = false;
      sub.remove();
      deactivateKeepAwake(TAG).catch(() => undefined); // the activity may already be gone: nothing to undo
    };
  }, [signedIn]);
}
