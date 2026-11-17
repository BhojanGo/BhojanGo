#!/bin/sh
# Make dev builds on the emulator load their JS through `adb reverse` (localhost:8081)
# instead of the emulator's NAT address 10.0.2.2:8081. Run it BEFORE the runner's
# `adb reverse` lines: `adb root` restarts adbd, which drops every reverse rule.
#   sh tools/mobile/metro-host.sh <device>
#
# Why (R9, 2026-11-16): an app force-stopped while it was still downloading its bundle
# over 10.0.2.2 (the runners' warm-up, or a flow's clearState) left a dead connection in
# the emulator's NAT; the next launch's bundle request never reached Metro, the packager
# socket aborted ("Software caused connection abort") and the first flow saw a black
# screen until it timed out (2 of 2 runs). Through adb reverse the same three launches
# pass (3 of 3). React Native reads the host from the metro.host system property, which
# survives clearState but not a reboot; setting it needs root (Google APIs images allow
# `adb root`, Play Store images do not: then the runners fall back to 10.0.2.2).
DEVICE="$1"
if [ "$(adb -s "$DEVICE" shell getprop metro.host | tr -d '\r')" = localhost ]; then exit 0; fi
timeout 30 adb -s "$DEVICE" root >/dev/null 2>&1
timeout 60 adb -s "$DEVICE" wait-for-device
if adb -s "$DEVICE" shell setprop metro.host localhost >/dev/null 2>&1; then
  echo "metro.host=localhost (JS through adb reverse)"
else
  echo "metro.host not set (no root on this image): JS loads over 10.0.2.2"
fi
