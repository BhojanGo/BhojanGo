// R9: what a screen shows when its data can't load (the API is down, the phone is
// offline, or a request hung past FIRST_LOAD_TIMEOUT_MS): a branded message that
// says why in one line, and Retry, which runs the load again.
//
//   const { status, data, error, retry } = useFirstLoad(() => getThings(), [id]);
//   if (status === "error" && !data) return <LoadError error={error} onRetry={retry} />;
//
// testIDs "load-error" (the block) and "load-retry" (the button) are what the
// offline Maestro flows look for (apps/<app>/.maestro/offline-sign-in.yaml).
import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Path } from "react-native-svg";

import { useI18n, type Translate } from "../i18n";
import { createFirstLoad, loadFailure, type LoadState } from "../load";
import { Button, T } from "./components";
import { SafeAreaView } from "./safe-area";
import { color, dark, radius, space } from "./theme";

export interface LoadErrorProps {
  /** What the load threw (decides the reason line: no connection, too slow, our servers, or the API's own message). */
  error: unknown;
  /** Runs the load again; the button shows it is busy until the promise settles. */
  onRetry: () => unknown;
  /** "dark" on BhojanGo Delivery's night screens. */
  tone?: "light" | "dark";
  /** Instead of "Can't reach BhojanGo" (e.g. "Your addresses didn't load"). */
  title?: string;
  /** Centre it in all the room there is (a whole screen's load failed). */
  fill?: boolean;
  /** Part of a screen that has its own primary action (e.g. a form under it): Retry is the
   *  secondary button, so the screen keeps one primary action (page checklist 1.2). */
  inline?: boolean;
  testID?: string;
  style?: StyleProp<ViewStyle>;
}

/**
 * The words for a failed load: the title ("Can't reach BhojanGo", or "This didn't load"
 * when the API refused) and why in one line. For a screen that keeps showing what it
 * has and only needs a line (a polling board): `${title}. ${reason}`.
 */
export function loadErrorText(error: unknown, t: Translate): { title: string; reason: string } {
  const kind = loadFailure(error);
  if (kind !== "refused") return { title: t("app.load_error.title"), reason: t(`app.load_error.${kind}`) };
  const message = (error as { message?: unknown } | null)?.message;
  return { title: t("app.load_error.title_refused"), reason: typeof message === "string" && message ? message : t("common.error") };
}

/** The error state: icon, title, why (one line), Retry. */
export function LoadError({ error, onRetry, tone = "light", title, fill, inline, testID = "load-error", style }: LoadErrorProps) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const live = useRef(true);
  useEffect(() => () => {
    live.current = false;
  }, []);
  const words = loadErrorText(error, t);
  const heading = title ?? words.title;
  const reason = words.reason;
  const onDark = tone === "dark";

  const retry = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await onRetry();
    } catch {
      // the screen shows the new failure
    } finally {
      if (live.current) setBusy(false);
    }
  };

  return (
    <View testID={testID} accessibilityRole="alert" accessibilityLiveRegion="polite"
      style={[styles.box, onDark ? styles.dark : styles.light, fill && styles.fill, style]}>
      <View style={[styles.icon, { backgroundColor: onDark ? dark.raised : color.peacockTint }]} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        <Svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke={onDark ? dark.link : color.peacock} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M2 8.8a15 15 0 0 1 4.2-2.6M9.9 5.1A15 15 0 0 1 22 8.8M5 12.6a10 10 0 0 1 4.3-2.3M14.6 10.6A10 10 0 0 1 19 12.6M8.5 16.4a5 5 0 0 1 7 0M12 20h.01M3 3l18 18" />
        </Svg>
      </View>
      <T testID="load-error-title" variant="h3" accessibilityRole="header" style={[styles.center, onDark && { color: dark.text }]}>{heading}</T>
      <T testID="load-error-reason" variant="body" style={[styles.center, { color: onDark ? dark.muted : color.muted }]}>{reason}</T>
      <Button testID="load-retry" title={t("app.load_error.retry")} accessibilityLabel={`${t("app.load_error.retry")}: ${heading}`}
        variant={onDark ? "rider" : inline ? "secondary" : "primary"} loading={busy} onPress={() => void retry()} style={styles.button} />
    </View>
  );
}

/**
 * The whole app couldn't start (the session check got no answer): LoadError on its
 * own screen, before any navigation. The root layouts show it while the session is
 * "unreachable"; Retry checks again. The person stays signed in.
 */
export function UnreachableScreen({ error, onRetry, tone = "light" }: { error: unknown; onRetry: () => unknown; tone?: "light" | "dark" }) {
  return (
    <SafeAreaView testID="unreachable-screen" style={{ flex: 1, backgroundColor: tone === "dark" ? dark.ground : color.porcelain }}>
      <LoadError error={error} onRetry={onRetry} tone={tone} fill />
    </SafeAreaView>
  );
}

/**
 * A screen's first load, with Retry (load.ts createFirstLoad): runs `load` now and
 * again when `deps` change. `retry` runs it again and resolves when it settles.
 */
export function useFirstLoad<T>(load: () => Promise<T>, deps: DependencyList): LoadState<T> & { retry: () => Promise<void> } {
  const [state, setState] = useState<LoadState<T>>({ status: "loading", data: null, error: null });
  const latest = useRef(load);
  useEffect(() => {
    latest.current = load;
  });
  const controller = useRef<ReturnType<typeof createFirstLoad<T>> | null>(null);
  useEffect(() => {
    const c = createFirstLoad(() => latest.current(), setState);
    controller.current = c;
    void c.run();
    return () => c.dispose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  const retry = useCallback(() => controller.current?.run() ?? Promise.resolve(), []);
  return { ...state, retry };
}

const styles = StyleSheet.create({
  box: { alignItems: "center", gap: space[3], padding: space[6], borderRadius: radius.card },
  light: { backgroundColor: color.white },
  dark: { backgroundColor: dark.surface },
  fill: { flex: 1, justifyContent: "center", backgroundColor: "transparent", borderRadius: 0 },
  icon: { width: 56, height: 56, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  center: { textAlign: "center" },
  button: { alignSelf: "center", minWidth: 160, marginTop: space[2] },
});
