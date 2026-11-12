// app.json plus local-only adjustments. Firebase's google-services.json comes
// with a real Firebase project; without it (local builds) push uses Expo's
// service only, so the reference is dropped rather than failing prebuild.
const fs = require("fs");
const path = require("path");

module.exports = ({ config }) => {
  const file = config.android && config.android.googleServicesFile;
  if (file && !fs.existsSync(path.join(__dirname, file))) {
    delete config.android.googleServicesFile;
  }
  return config;
};
