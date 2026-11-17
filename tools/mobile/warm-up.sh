#!/bin/sh
# Open a dev build once so Metro builds its bundle before the first Maestro flow, and
# close it only after the app has finished loading that bundle.
#   sh tools/mobile/warm-up.sh <device> <package> <metro log> [timeout seconds]
#
# Why not "close it 10 s after Metro says Bundled" (what the runners did until R9):
# Metro logs "Bundled" when the build is done, but the emulator then still downloads
# the (large, unminified) dev bundle over its NAT address 10.0.2.2:8081. Force-stopping
# the app mid-download left a dead connection in the emulator's network layer, and the
# NEXT launch (the first flow, after clearState) hung on it: its bundle request never
# reached Metro, the packager socket aborted ("Software caused connection abort") and
# the app stayed a black screen until the flow timed out. Every later flow passed.
# Reproduced 2 of 2 on 2026-11-16 (first run FAIL, second PASS, adb reverse and the adb
# server unchanged). Two fixes: this wait, and tools/mobile/metro-host.sh, which sends the
# JS through adb reverse so a killed download can't poison the next launch at all.
DEVICE="$1"; PKG="$2"; LOG="$3"; LIMIT="${4:-300}"
adb -s "$DEVICE" logcat -c >/dev/null 2>&1
adb -s "$DEVICE" shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
end=$(( $(date +%s) + LIMIT ))
until grep -q "Android Bundled" "$LOG" || [ "$(date +%s)" -ge "$end" ]; do sleep 3; done
grep -q "Android Bundled" "$LOG" || { echo "warm-up: Metro never bundled $PKG"; tail -40 "$LOG"; }
# React Native logs this once the JS bundle is loaded and the first screen starts.
until adb -s "$DEVICE" logcat -d -s "unknown:BridgelessReact" 2>/dev/null | grep -q "startSurface(surfaceId = 0): Execute" \
  || [ "$(date +%s)" -ge "$end" ]; do sleep 2; done
adb -s "$DEVICE" logcat -d -s "unknown:BridgelessReact" 2>/dev/null | grep -q "startSurface(surfaceId = 0): Execute" \
  || echo "warm-up: $PKG did not finish loading its bundle in ${LIMIT}s"
sleep 3   # let the first screen's requests start before closing
adb -s "$DEVICE" shell am force-stop "$PKG" >/dev/null 2>&1
