# ADR-006: Expo with React Native

## Status
Accepted

## Context
Need cross-platform mobile app for customers and drivers with push notifications, maps, and location tracking.

## Decision
Expo SDK with React Native for both iOS and Android.

## Consequences
Faster development cycle, OTA updates via EAS, managed native modules. Some native module limitations.

## Alternatives Considered
- Bare React Native CLI (more setup overhead)
- Flutter (team knows React, not Dart)
- Native (2x development cost)
