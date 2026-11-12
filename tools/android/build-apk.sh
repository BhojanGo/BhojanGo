#!/bin/sh
# Build an Expo app's Android debug APK inside Linux (no Windows path limits,
# no OneDrive locks). Runs in reactnativecommunity/react-native-android; see
# `make apk APP=customer`. The APK loads its JavaScript from Metro on the host
# (`pnpm --filter @bhojango/<app> start`), so rebuild only when native code changes.
set -eu
APP="${1:?usage: build-apk.sh <customer|rider|partner>}"
ARCH="${ARCH:-x86_64}" # the emulator; arm64-v8a for phones

mkdir -p /work
# The repo without host node_modules or generated native projects.
tar -C /src --exclude=node_modules --exclude='apps/*/android' --exclude='apps/*/ios' --exclude=.git \
  --exclude=backend --exclude='apps/*/.next' -cf - . | tar -C /work -xf -
cd /work
corepack enable >/dev/null 2>&1 || npm install -g pnpm@9 >/dev/null
pnpm install --frozen-lockfile --store-dir /pnpm-store >/dev/null
cd "apps/$APP"
CI=1 npx expo prebuild --platform android --no-install
cd android
./gradlew assembleDebug -PreactNativeArchitectures="$ARCH" --console=plain -q
mkdir -p /out
cp app/build/outputs/apk/debug/app-debug.apk "/out/$APP-debug.apk"
echo "built /out/$APP-debug.apk"
