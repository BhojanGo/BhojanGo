// R28: the pure part of lib/awake.ts (no native module), for node --test.
import type { AppStateStatus } from "react-native";
export const RETRY_MS = 2000;
export const MAX_TRIES = 5;

/** Hold the screen on now? Only signed in and in the foreground (in the background Android can't). */
export function wantAwake(signedIn: boolean, app: AppStateStatus | string | null): boolean {
  return signedIn && app === "active";
}

/** Activate, retrying a failure up to `tries` times `waitMs` apart; true once it held. */
export async function holdAwake(activate: () => Promise<void>, still: () => boolean, tries = MAX_TRIES,
  waitMs = RETRY_MS, sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))): Promise<boolean> {
  for (let i = 0; i < tries && still(); i++) {
    try {
      await activate();
      return true;
    } catch (e) {
      console.info(`[awake] activate failed (${i + 1}/${tries}): ${e instanceof Error ? e.message : String(e)}`);
      if (i + 1 < tries) await sleep(waitMs);
    }
  }
  return false;
}
