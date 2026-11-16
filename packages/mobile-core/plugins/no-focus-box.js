// Expo config plugin (R8), used by all three apps' app.config.js: turns off
// Android's default focus highlight in the app theme.
//
// Why: after the language menu (a Modal) closes, or after a Back key press,
// Android leaves the pressed control focused and, outside touch mode, draws its
// default focus highlight: a grey rectangle over the control's whole bounds,
// ignoring its rounded shape (the grey square behind the "EN" pill on the home
// screen). The apps' controls show their own pressed states; nothing relies on
// the platform's grey box. TalkBack's focus ring is separate and unaffected.
// Native change: it applies to builds made after it (expo prebuild / a new APK).
// (Android 8+ has the attribute; older versions ignore it.)
"use strict";

const { AndroidConfig, withAndroidStyles } = require("expo/config-plugins");

module.exports = function withNoFocusBox(config) {
  return withAndroidStyles(config, (c) => {
    c.modResults = AndroidConfig.Styles.assignStylesValue(c.modResults, {
      add: true,
      name: "android:defaultFocusHighlightEnabled",
      value: "false",
      parent: AndroidConfig.Styles.getAppThemeGroup(),
    });
    return c;
  });
};
