// BhojanGo on Railway, as code (Railway IaC). Applied with the steps in
// docs/runbooks/railway-deploy.md:
//   railway config plan → (review) → railway config apply
//
// Environments:
//   QA          from dev:  the zero-spend fakes, seeded with random passwords, small and capped
//   staging     from dev:  the same, plus a TCP proxy to Postgres for seeding and backups
//   production  from main: live providers; refuses the fakes at start-up (shared/config.py)
// The AWS Terraform (infra/terraform) stays as the scale-up path.
//
// Every secret is preserve(): set once as a sealed variable, never in this file.
// Don't use ctx.randomString() for secrets: it's a hash of the environment name
// and a label, so anyone with this file can recompute it.
import { bucket, defineRailway, github, group, preserve, redis, service, volume, type VariableValue } from "railway/iac";

type Env = Record<string, string | VariableValue>;

const REPO = "BhojanGo/BhojanGo";
const GIB = 1024 ** 3;

export default defineRailway((ctx, project) => {
  const prod = ctx.isEnvironment("production");
  const qa = ctx.isEnvironment("QA");
  const branch = prod ? "main" : "dev";
  const appEnv = prod ? "production" : qa ? "qa" : "staging";
  const src = (rootDirectory?: string) => github(REPO, { branch, ...(rootDirectory ? { rootDirectory } : {}) });
  // QA: hard caps per service (CPU in vCPUs) so a runaway process can't run up
  // the bill. Railway's spending limit is per workspace, not per project.
  const cap = (cpu: number, memoryGiB: number) =>
    qa ? { limitOverride: { containers: { cpu, memoryBytes: Math.round(memoryGiB * GIB) } } } : {};

  // ── Data ───────────────────────────────────────────────────────────────
  // Postgres with PostGIS: Railway's Postgres image plus the PostGIS package
  // (infra/railway/postgis.Dockerfile); data on a volume. Railway's Postgres
  // template has no PostGIS and Railway doesn't add extensions to it.
  // Pin the volume's region: left out, a plan wants to move it (a destructive change).
  const pgData = volume("postgres-data", { sizeMB: prod ? 10_240 : 2_048, region: "us-west2" });
  const postgres = service("postgres", {
    source: src(),
    build: { builder: "DOCKERFILE", dockerfilePath: "infra/railway/postgis.Dockerfile",
             watchPatterns: ["infra/railway/postgis.Dockerfile"] },
    volumeMounts: { "/var/lib/postgresql/data": pgData },
    deploy: { ...cap(1, 1) },
    env: {
      POSTGRES_USER: "bhojango",
      POSTGRES_DB: "bhojango",
      POSTGRES_PASSWORD: preserve(), // sealed; generate once: openssl rand -hex 24
      PGDATA: "/var/lib/postgresql/data/pgdata",
    },
    // Staging only: a public TCP proxy for seeding and backups. QA and production
    // keep Postgres private; reach it with `railway connect postgres --tunnel-only`.
    tcp: prod || qa ? [] : [5432],
  });
  const pgUrl = "postgresql+asyncpg://bhojango:${{postgres.POSTGRES_PASSWORD}}@postgres.railway.internal:5432/bhojango";

  const cache = redis("redis");
  // Same Redis databases as compose: core_api 0, realtime 3, the event bus 5.
  const redisDb = (n: number) => `\${{redis.REDIS_URL}}/${n}`;

  // The browser origins core_api and realtime accept (CORS): web and admin.
  const origins = '["https://${{web.RAILWAY_PUBLIC_DOMAIN}}","https://${{admin.RAILWAY_PUBLIC_DOMAIN}}"]';

  // ── Settings every backend deployable shares ───────────────────────────
  const backendEnv: Env = {
    APP_ENV: appEnv,
    DATABASE_URL: pgUrl,
    // Events: Redis Streams instead of SNS/SQS (backend/shared/bus.py).
    EVENT_BUS: "redis",
    EVENT_BUS_REDIS_URL: redisDb(5),
    INTERNAL_SERVICE_SECRET: preserve(), // sealed; openssl rand -hex 32, the same on all three
    CORE_API_URL: "http://core-api.railway.internal:8001",
    JWKS_URL: "http://core-api.railway.internal:8001/.well-known/jwks.json",
    CORS_ORIGINS: prod ? preserve() : origins, // production: the custom domains
    // Providers: local fakes until each account exists (docs/11_Integration_Setup_Guide.md).
    // Production refuses to start with a fake or the fixed OTP (shared/config.py).
    PAYMENT_PROVIDER: prod ? "live" : "fake",
    PAYOUT_PROVIDER: prod ? "live" : "fake",
    SMS_PROVIDER: prod ? "live" : "log",
    PUSH_PROVIDER: prod ? "live" : "log",
    EMAIL_PROVIDER: prod ? "sendgrid" : "log",
    ...(prod ? { OTP_FIXED_CODE: "" } : {}),
    ROUTING_PROVIDER: "straight_line",
    LOG_FORMAT: "json",
  };

  // Python services listen on 0.0.0.0. Not `::`: asyncio sets IPV6_V6ONLY on a
  // socket bound to ::, so uvicorn would take IPv6 only, and Railway's health check
  // and public edge connect over IPv4 (verified on QA, 2026-11-14). The private
  // network resolves *.railway.internal to IPv4 too in environments created after
  // 2025-10-16; an older (IPv6-only) environment needs a dual-stack socket instead.
  const backend = (name: string, dir: string, port: number, app: string, extra: Env,
                   opts: { preDeploy?: string; cpu: number; memoryGiB: number }) =>
    service(name, {
      source: src("backend"),
      build: { builder: "DOCKERFILE", dockerfilePath: `${dir}/Dockerfile`,
               watchPatterns: [`backend/${dir}/**`, "backend/shared/**", "backend/pyproject.toml", "backend/uv.lock"] },
      start: `uvicorn ${app} --host 0.0.0.0 --port ${port} --timeout-keep-alive 130`,
      healthcheck: "/health/ready",
      healthcheckTimeout: 120,
      ...(opts.preDeploy ? { preDeploy: opts.preDeploy } : {}),
      deploy: { ...cap(opts.cpu, opts.memoryGiB) },
      env: { ...backendEnv, PORT: String(port), ...extra },
    });

  // ── Backend ────────────────────────────────────────────────────────────
  // core_api: migrations run before each deploy goes live (pre-deploy, in its
  // own container on the private network), so a failed migration stops the
  // release and the old version keeps serving.
  // Uploads: a Railway bucket through the S3 API (public endpoint only; buckets
  // can't be public, so the API hands out presigned URLs).
  // A bucket needs a region (sjc, iad, ams, sin); it can't change later. San Jose,
  // next to the services' default US West region.
  const uploads = bucket("uploads", { region: "sjc" });
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
    S3_ADDRESSING_STYLE: preserve(), // its urlStyle: "virtual" (new buckets) or "path"
    FAKE_PAYMENT_WEBHOOK_URL: "http://core-api.railway.internal:8001/api/v1/payments/fake/webhook",
    FAKE_PAYMENT_AUTO_COMPLETE_SECONDS: "2",
    FAKE_PAYMENT_WEBHOOK_SECRET: preserve(), // sealed outside local dev
    ALERT_WEBHOOK_TOKEN: preserve(),
  }, { preDeploy: "alembic upgrade head", cpu: 1, memoryGiB: 1 });

  const realtime = backend("realtime", "realtime", 8004, "app.main:app", {
    SERVICE_NAME: "realtime",
    REDIS_URL: redisDb(3),
  }, { cpu: 0.5, memoryGiB: 0.5 });

  const worker = backend("worker", "worker", 8006, "app.main:app", {
    SERVICE_NAME: "worker",
    REDIS_URL: redisDb(0),
    DB_POOL_SIZE: "5",
    REALTIME_INTERNAL_URL: "http://realtime.railway.internal:8004", // the batch engine (task 43)
  }, { cpu: 0.5, memoryGiB: 0.5 });

  // ── Web and admin (Next.js, infra/docker/next-app.Dockerfile) ──────────
  // NEXT_PUBLIC_* are baked into the browser bundle at build time (Dockerfile
  // ARGs), so they point at the public domains. Outside production the two
  // frontends sleep when idle (Railway "Serverless"); the backends don't: they
  // run timers (dispatch, outbox, sweeps) that must keep going.
  const next = (name: string, pkg: string, dir: string, extra: Env) =>
    service(name, {
      source: src(),
      build: { builder: "DOCKERFILE", dockerfilePath: "infra/docker/next-app.Dockerfile",
               watchPatterns: [`${dir}/**`, "packages/**", "pnpm-lock.yaml", "infra/docker/next-app.Dockerfile"] },
      healthcheck: "/",
      healthcheckTimeout: 120,
      deploy: { ...(prod ? {} : { sleepApplication: true }), ...cap(0.5, 0.5) },
      env: {
        APP: pkg, APP_DIR: dir, PORT: "3000",
        CORE_API_URL: "http://core-api.railway.internal:8001",
        REALTIME_URL: "http://realtime.railway.internal:8004",
        NEXT_PUBLIC_CORE_URL: `https://\${{core-api.RAILWAY_PUBLIC_DOMAIN}}`,
        NEXT_PUBLIC_REALTIME_URL: `https://\${{realtime.RAILWAY_PUBLIC_DOMAIN}}`,
        ...extra,
      },
    });

  const web = next("web", "@bhojango/web", "apps/web", {
    CORE_API_INTERNAL_URL: "http://core-api.railway.internal:8001",
    NEXT_PUBLIC_APP_URL: prod ? preserve() : `https://\${{web.RAILWAY_PUBLIC_DOMAIN}}`, // production: the custom domain
  });
  const admin = next("admin", "@bhojango/admin", "apps/admin", {});

  return project("bhojango", {
    environments: ["QA", "staging", "production"],
    resources: [
      group("Data", [postgres, pgData, cache]),
      group("Backend", [coreApi, realtime, worker, uploads]),
      group("Frontends", [web, admin]),
    ],
  });
});
