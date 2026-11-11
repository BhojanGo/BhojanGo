// Monorepo Metro config: pnpm keeps packages in the workspace-root
// node_modules/.pnpm store and links workspace packages such as
// @bhojango/mobile-core, so Metro must watch and resolve from the root too.
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);
config.watchFolders = [workspaceRoot];
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];

// web/admin hoist React 18.3 to the workspace root, but Expo 51 needs this
// app's React 18.2. Resolve react and react-native from the app for every
// importer, so packages under the root store don't load a second React.
const SINGLETONS = /^(react|react-native)(\/|$)/;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (SINGLETONS.test(moduleName)) {
    return context.resolveRequest(
      { ...context, originModulePath: path.join(projectRoot, "package.json") },
      moduleName,
      platform,
    );
  }
  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
