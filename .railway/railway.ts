// BhojanGo on Railway: the pilot's hosting, as code (Railway IaC).
//
// Nothing here has been applied; no Railway account or project exists yet.
// Going live is the list in docs/runbooks/railway-deploy.md:
//   railway login → railway link → railway config plan → (review) → railway config apply
//
// Two environments: "staging" builds from the dev branch, "production" from main.
// The AWS Terraform (infra/terraform) stays as the scale-up path.
//
// Every secret is preserve(): it's set once in the dashboard as a sealed
// variable and never lives in this file.
import { bucket, defineRailway, github, group, preserve, redis, service, volume, type VariableValue } from "railway/iac";

type Env = Record<string, string | VariableValue>;

const REPO = "BhojanGo/BhojanGo";

export default defineRailway((ctx, project) => {
  const prod = ctx.isEnvironment("production");
  const branch = prod ? "main" : "dev";
  const env = prod ? "production" : "staging";
  const src = (rootDirectory?: string) => github(REPO, { branch, ...(rootDirectory ? { rootDirectory } : {}) });

  // ── Data ───────────────────────────────────────────────────────────────
  // Postgres with PostGIS: Railway's own Postgres image plus the PostGIS
  // package (infra/railway/postgis.Dockerfile); data on a volume. Railway's
  // managed postgres() has no PostGIS, so this is a service, not a database.
  const pgData = volume("postgres-data", { sizeMB: prod ? 10_240 : 2_048 });
  const postgres = service("postgres", {
    source: src(),
    build: { builder: "DOCKERFILE", dockerfilePath: "infra/railway/postgis.Dockerfile",
             watchPatterns: ["infra/railway/postgis.Dockerfile"] },
    volumeMounts: { "/var/lib/postgresql/data": pgData },
    env: {
      POSTGRES_USER: "bhojango",
      POSTGRES_DB: "bhojango",
      POSTGRES_PASSWORD: preserve(), // sealed; generate once: openssl rand -hex 24
      PGDATA: "/var/lib/postgresql/data/pgdata",
    },
    tcp: prod ? [] : [5432], // staging only: a TCP proxy for `make seed`-style scripts and backups
  });
  const pgUrl = "postgresql+asyncpg://bhojango:${{postgres.POSTGRES_PASSWORD}}@postgres.railway.internal:5432/bhojango";

  const cache = redis("redis");
  // Same Redis databases as compose: core_api 0, realtime 3, the event bus 5.
  const redisDb = (n: number) => `\${{redis.REDIS_URL}}/${n}`;

  // ── Settings every backend deployable shares ───────────────────────────
  const backendEnv: Env = {
    APP_ENV: env,
    DATABASE_URL: pgUrl,
    // Events: Redis Streams instead of SNS/SQS (backend/shared/bus.py).
    EVENT_BUS: "redis",
    EVENT_BUS_REDIS_URL: redisDb(5),
    INTERNAL_SERVICE_SECRET: preserve(), // sealed; openssl rand -hex 32
    CORE_API_URL: "http://core-api.railway.internal:8001",
    JWKS_URL: "http://core-api.railway.internal:8001/.well-known/jwks.json",
    CORS_ORIGINS: preserve(), // JSON list of the web and admin origins, e.g. ["https://bhojango.com","https://admin.bhojango.com"]
    // Providers: local fakes until each account exists (docs/11_Integration_Setup_Guide.md).
    PAYMENT_PROVIDER: prod ? "live" : "fake",
    SMS_PROVIDER: prod ? "live" : "log",
    PUSH_PROVIDER: prod ? "live" : "log",
    EMAIL_PROVIDER: prod ? "sendgrid" : "log",
    ROUTING_PROVIDER: "straight_line",
  };

  // Python services listen on :: so both the public edge and the private
  // network (IPv6) reach them.
  const backend = (name: string, dir: string, port: number, app: string, extra: Env, opts: { preDeploy?: string } = {}) =>
    service(name, {
      source: src("backend"),
      build: { builder: "DOCKERFILE", dockerfilePath: `${dir}/Dockerfile`,
               watchPatterns: [`backend/${dir}/**`, "backend/shared/**", "backend/pyproject.toml", "backend/uv.lock"] },
      start: `uvicorn ${app} --host :: --port ${port}`,
      healthcheck: "/health/ready",
      healthcheckTimeout: 120,
      ...opts,
      env: { ...backendEnv, PORT: String(port), ...extra },
    });

  // ── Backend ────────────────────────────────────────────────────────────
  // core_api: migrations run before each deploy goes live (preDeploy), so a
  // failed migration stops the release and the old version keeps serving.
  // Uploads (delivery and problem photos, documents): a Railway bucket through
  // the S3 API. Not a volume: volumes are owned by root and the services run as
  // a non-root user (security pass). Values from `railway bucket credentials`.
  const uploads = bucket("uploads");
  const coreApi = backend("core-api", "core_api", 8001, "core_api.main:app", {
    SERVICE_NAME: "core-api",
    REDIS_URL: redisDb(0),
    JWKS_URL: "", // core_api signs; it publishes the JWKS itself
    JWT_PRIVATE_KEY: preserve(), // sealed; required outside development (docs/security/report.md)
    STORAGE_PROVIDER: "s3",
    UPLOADS_BUCKET: preserve(), // the bucket's bucketName
    AWS_ENDPOINT_URL: preserve(), // its endpoint
    AWS_REGION: preserve(), // its region
    AWS_ACCESS_KEY_ID: preserve(), // sealed
    AWS_SECRET_ACCESS_KEY: preserve(), // sealed
    S3_ADDRESSING_STYLE: preserve(), // its urlStyle: "virtual" or "path"
    FAKE_PAYMENT_WEBHOOK_URL: "http://core-api.railway.internal:8001/api/v1/payments/fake/webhook",
    FAKE_PAYMENT_AUTO_COMPLETE_SECONDS: "2",
    ALERT_WEBHOOK_TOKEN: preserve(),
  }, {
    preDeploy: "alembic upgrade head",
  });

  const realtime = backend("realtime", "realtime", 8004, "app.main:app", {
    SERVICE_NAME: "realtime",
    REDIS_URL: redisDb(3),
  });

  const worker = backend("worker", "worker", 8006, "app.main:app", {
    SERVICE_NAME: "worker",
    REDIS_URL: redisDb(0),
    DB_POOL_SIZE: "5",
  });

  // ── Web and admin (Next.js, infra/docker/next-app.Dockerfile) ──────────
  // NEXT_PUBLIC_* are baked into the browser bundle at build time, so they
  // must point at the public domains (set once the domains exist).
  const next = (name: string, pkg: string, dir: string, extra: Env) =>
    service(name, {
      source: src(),
      build: { builder: "DOCKERFILE", dockerfilePath: "infra/docker/next-app.Dockerfile",
               watchPatterns: [`${dir}/**`, "packages/**", "pnpm-lock.yaml", "infra/docker/next-app.Dockerfile"] },
      healthcheck: "/",
      healthcheckTimeout: 120,
      env: {
        APP: pkg, APP_DIR: dir, PORT: "3000",
        CORE_API_URL: "http://core-api.railway.internal:8001",
        REALTIME_URL: "http://realtime.railway.internal:8004",
        NEXT_PUBLIC_CORE_URL: `https://\${{core-api.RAILWAY_PUBLIC_DOMAIN}}`,
        NEXT_PUBLIC_REALTIME_URL: `https://\${{realtime.RAILWAY_PUBLIC_DOMAIN}}`,
        NEXT_PUBLIC_WORKER_URL: `https://\${{worker.RAILWAY_PUBLIC_DOMAIN}}`,
        ...extra,
      },
    });

  const web = next("web", "@bhojango/web", "apps/web", {
    CORE_API_INTERNAL_URL: "http://core-api.railway.internal:8001",
    NEXT_PUBLIC_APP_URL: preserve(), // https://bhojango.com once the domain exists
  });
  const admin = next("admin", "@bhojango/admin", "apps/admin", {});

  return project("bhojango", {
    environments: ["staging", "production"],
    resources: [
      group("Data", [postgres, pgData, cache]),
      group("Backend", [coreApi, realtime, worker, uploads]),
      group("Frontends", [web, admin]),
    ],
  });
});
