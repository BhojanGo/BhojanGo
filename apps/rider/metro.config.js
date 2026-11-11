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

module.exports = config;
