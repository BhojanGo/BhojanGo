# ADR-006: Expo with React Native

## Status
Accepted. Amended by ADR-011 (Nov 2026).

## Context
Need cross-platform mobile app for customers and drivers with push notifications, maps, and location tracking.

## Decision
Expo SDK with React Native for both iOS and Android.

**Amended (Nov 2026):** three apps on the latest Expo SDK (SDK 58 at the time of
ADR-011) with EAS Build/Submit/Update: `apps/customer` (`com.bhojango.app`),
`apps/rider` (`com.bhojango.rider`) and `apps/partner` (`com.bhojango.partner`,
tablets, from P19), sharing `packages/mobile-core`. Native package versions come from
the SDK (`npx expo install --fix`). The apps run SDK 51 today; P16–P19 move them.

## Consequences
Faster development cycle, OTA updates via EAS, managed native modules. Some native module limitations.

## Alternatives Considered
- Bare React Native CLI (more setup overhead)
- Flutter (team knows React, not Dart)
- Native (2x development cost)
