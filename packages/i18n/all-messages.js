// Every language's messages in one module, for the Expo apps: Metro bundles them
// all (the app works offline and switches language without a download). The
// website loads one language at a time from ./messages/<lang>.json instead.
module.exports = {
  en: require("./messages/en.json"),
  hi: require("./messages/hi.json"),
  te: require("./messages/te.json"),
  ta: require("./messages/ta.json"),
  kn: require("./messages/kn.json"),
  mr: require("./messages/mr.json"),
  bn: require("./messages/bn.json"),
  es: require("./messages/es.json"),
};
