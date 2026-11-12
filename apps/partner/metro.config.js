// Monorepo Metro config: workspace packages (@bhojango/mobile-core, ui,
// api-client) live outside the app, so Metro watches and resolves from the
// workspace root too. node_modules is hoisted (one React for the monorepo).
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);
config.watchFolders = [workspaceRoot];
config.resolver.nodeModulesPaths = [path.resolve(projectRoot, "node_modules"), path.resolve(workspaceRoot, "node_modules")];

module.exports = config;
