// app.json plus local-only adjustments. Firebase's google-services.json comes
// with a real Firebase project; without it (local builds) push uses Expo's
// service only, so the reference is dropped rather than failing prebuild.
const fs = require("fs");
const path = require("path");

const { applyStoreConfig } = require("@bhojango/mobile-core/plugins/store-config");

module.exports = ({ config }) => {
  const file = config.android && config.android.googleServicesFile;
  if (file && !fs.existsSync(path.join(__dirname, file))) {
    delete config.android.googleServicesFile;
  }
  // No grey focus box on Android controls (packages/mobile-core/plugins/no-focus-box.js).
  config.plugins = [...(config.plugins || []), require("@bhojango/mobile-core/plugins/no-focus-box")];
  // R19: store ids from config/store.json; a production build stops here on a placeholder id,
  // an http/localhost address or EXPO_PUBLIC_APP_ENV other than production (eas.json sets it).
  return applyStoreConfig(config, "rider");
};
