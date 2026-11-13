# Next.js apps (apps/web, apps/admin) for the local "all" profile.
# Build from the repo root:
#   docker build -f infra/docker/next-app.Dockerfile \
#     --build-arg APP=@bhojango/web --build-arg APP_DIR=apps/web .
# Node 24 LTS per ADR-011.
# Debian 13 (trixie), as the Python images: its zlib has the minizip fix (security pass).
ARG NODE_IMAGE=node:24-trixie-slim

FROM ${NODE_IMAGE} AS prune
ARG APP
WORKDIR /repo
RUN npm install -g turbo@2.9.4
COPY . .
RUN turbo prune "${APP}" --docker

FROM ${NODE_IMAGE} AS build
ARG APP
ARG APP_DIR
# Rewrites in next.config.mjs are resolved at build time; these point the
# server-side proxy at the core_api container.
ARG CORE_API_URL=http://core-api:8001
ARG REALTIME_URL=http://realtime:8004
ENV USER_SVC_URL=${CORE_API_URL} \
    REALTIME_SVC_URL=${REALTIME_URL} \
    RESTAURANT_SVC_URL=${CORE_API_URL} \
    ORDER_SVC_URL=${CORE_API_URL} \
    PAYMENT_SVC_URL=${CORE_API_URL} \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /repo
RUN corepack enable
COPY --from=prune /repo/out/json/ .
COPY .npmrc ./
RUN pnpm install --frozen-lockfile
COPY --from=prune /repo/out/full/ .
RUN pnpm turbo build --filter="${APP}..."

FROM ${NODE_IMAGE} AS run
ARG APP_DIR
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 APP_DIR=${APP_DIR}
WORKDIR /repo
# Security (trivy): Debian security fixes, and no npm at runtime (its bundled
# undici and brace-expansion had HIGH CVEs; next is started directly).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/* \
 && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx
# Security (trivy DS002): run as the image's unprivileged "node" user; it owns the
# app so Next can write its cache (ISR). next is started directly (no pnpm at runtime).
COPY --from=build --chown=node:node /repo .
USER node
EXPOSE 3000
CMD ["sh", "-c", "cd \"$APP_DIR\" && exec /repo/node_modules/.bin/next start -p \"${PORT:-3000}\""]
