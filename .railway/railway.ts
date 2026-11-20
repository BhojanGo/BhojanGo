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

  // QA's own addresses on bhojango.com (custom domains, 2026-11-19; DNS at GoDaddy, certificates by Railway).
  // Staging keeps Railway's generated domains; production's are set by hand (docs/launch/production-config.md).
  const QA_HOSTS = { web: "qa.bhojango.com", admin: "admin.qa.bhojango.com", api: "api.qa.bhojango.com", rt: "rt.qa.bhojango.com" };
  const publicUrl = (svc: "web" | "admin" | "core-api" | "realtime") => {
    if (qa) return `https://${QA_HOSTS[({ web: "web", admin: "admin", "core-api": "api", realtime: "rt" } as const)[svc]]}`;
    return `https://\${{${svc}.RAILWAY_PUBLIC_DOMAIN}}`;
  };

  // The browser origins core_api and realtime accept (CORS): web and admin. QA also keeps its old
  // *.up.railway.app origins until 2026-11-26 (7 days after the switch; docs/STATUS.md), then drops them.
  // They're named: once a service has a custom domain, RAILWAY_PUBLIC_DOMAIN resolves to that instead.
  const railwayOrigins = ["https://${{web.RAILWAY_PUBLIC_DOMAIN}}", "https://${{admin.RAILWAY_PUBLIC_DOMAIN}}"];
  const QA_OLD_ORIGINS = ["https://web-qa-3fd3b3f8.up.railway.app", "https://admin-qa-df130aa4.up.railway.app"]; // until 2026-11-26
  const origins = JSON.stringify(qa ? [publicUrl("web"), publicUrl("admin"), ...QA_OLD_ORIGINS] : railwayOrigins);

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
    // Production refuses to start with a fake, the fixed OTP or the fixed delivery PIN (shared/config.py).
    // Production (R19, Srini's decisions): email through Amazon SES; sign-in codes through Twilio
    // Verify (core-api, OTP_PROVIDER below; no sender number or 10DLC); order updates by push (Expo),
    // so no SMS at all ("off": chosen, not a fake).
    PAYMENT_PROVIDER: prod ? "live" : "fake",
    PAYOUT_PROVIDER: prod ? "live" : "fake",
    SMS_PROVIDER: prod ? "off" : "log",
    PUSH_PROVIDER: prod ? "live" : "log",
    EMAIL_PROVIDER: prod ? "ses" : "log",
    ...(prod ? { OTP_FIXED_CODE: "", DELIVERY_PIN_FIXED: "" } : {}),
    // Error reports (Sentry, free plan; shared/observability.py): one backend project, sealed.
    ...(prod ? { SENTRY_DSN: preserve() } : {}),
    ROUTING_PROVIDER: "straight_line",
    LOG_FORMAT: "json",
    // The client's address for rate limits (sign-in, OTP) and logs: Railway's edge puts it in
    // X-Real-IP and overwrites one a client sends. The socket peer is Railway's proxy
    // (100.64.x.x), and X-Forwarded-For ends in edge hops (shared/client_ip.py).
    CLIENT_IP_HEADER: "X-Real-IP",
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
    GEOIP: "1", // build arg: fetch DB-IP's free City Lite for the website's "near you" hint
    JWKS_URL: "", // core_api signs; it publishes the JWKS itself
    JWT_PRIVATE_KEY: preserve(), // sealed; required outside development (docs/security/report.md)
    STORAGE_PROVIDER: "s3",
    UPLOADS_BUCKET: preserve(), // the bucket's bucketName
    AWS_ENDPOINT_URL: preserve(), // its endpoint
    AWS_REGION: preserve(), // its region
    AWS_ACCESS_KEY_ID: preserve(), // sealed
    AWS_SECRET_ACCESS_KEY: preserve(), // sealed
    S3_ADDRESSING_STYLE: preserve(), // its urlStyle: "virtual" (new buckets) or "path"
    ALERT_WEBHOOK_TOKEN: preserve(),
    // QA: links in emails, Stripe's returns and payout onboarding use QA's own addresses (production: set by hand).
    ...(qa ? { PUBLIC_WEB_URL: publicUrl("web"), PUBLIC_API_URL: publicUrl("core-api") } : {}),
    // The fake payment gateway: every environment but production.
    ...(prod ? {} : {
      FAKE_PAYMENT_WEBHOOK_URL: "http://core-api.railway.internal:8001/api/v1/payments/fake/webhook",
      FAKE_PAYMENT_AUTO_COMPLETE_SECONDS: "2",
      FAKE_PAYMENT_WEBHOOK_SECRET: preserve(), // sealed outside local dev
    }),
    // Production only (R19). core-api refuses to start without the public https addresses,
    // IDENTITY_DATA_KEYS and a way to send sign-in codes (shared/config.py core_api_production_problems).
    // Values are set once in Railway (sealed when secret): docs/launch/production-config.md.
    ...(prod ? {
      PUBLIC_WEB_URL: preserve(), // the website's custom domain, https://<domain> (reset links, Stripe returns)
      PUBLIC_API_URL: preserve(), // the API's custom domain, https://api.<domain> (payout onboarding links)
      IDENTITY_DATA_KEYS: preserve(), // sealed; python tools/secrets/identity_data_keys.py, once
      STRIPE_SECRET_KEY: preserve(), // sealed; Stripe live (sk_live_ or a restricted rk_live_)
      STRIPE_PUBLISHABLE_KEY: preserve(), // Stripe live (pk_live_); handed to the checkouts by the API
      STRIPE_WEBHOOK_SECRET: preserve(), // sealed; payments endpoint
      STRIPE_CONNECT_WEBHOOK_SECRET: preserve(), // sealed; Connect endpoint
      STRIPE_PAYOUTS_WEBHOOK_SECRET: preserve(), // sealed; transfers endpoint
      TAX_PROVIDER: "stripe_tax",
      OTP_PROVIDER: "twilio_verify",
      TWILIO_ACCOUNT_SID: preserve(), // sealed
      TWILIO_AUTH_TOKEN: preserve(), // sealed
      TWILIO_VERIFY_SERVICE_SID: preserve(), // sealed; Verify service (VA...)
    } : {}),
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
    // QA only: the demo rider delivers the demo customers' orders through the normal APIs
    // (worker/app/demo_sim). Never staging or production: production refuses to start with it.
    ...(qa ? { DEMO_RIDER_SIM: "1" } : {}),
    // Production only (R20): the review simulator plays the review kitchen and delivery partner for app store
    // reviewers' orders in the hidden review city, and touches nothing else (worker/app/demo_sim/review.py).
    // "1" while a build is in store review, "0" otherwise: docs/launch/go-live.md step 14.
    ...(prod ? { REVIEW_SIM: "0" } : {}),
    // Production email: Amazon SES (shared/providers/email.py SesEmail), an IAM user allowed
    // ses:SendEmail only. The worker refuses to start without these (worker/app/main.py).
    ...(prod ? {
      SES_REGION: "us-west-2", // where the domain identity is verified (Oregon)
      SES_ACCESS_KEY_ID: preserve(), // sealed
      SES_SECRET_ACCESS_KEY: preserve(), // sealed
      EMAIL_FROM: preserve(), // e.g. orders@<domain>: an address on the domain verified in SES
      EMAIL_FROM_NAME: "BhojanGo",
    } : {}),
  }, { cpu: 0.5, memoryGiB: 0.5 });

  // ── Backups (R22) ──────────────────────────────────────────────────────
  // 1. Railway's volume backups of postgres-data: daily (kept 6 days) and weekly (kept 27 days), set on the
  //    volume in Railway (QA: turned on 2026-11-20; production: go-live step 3). Railway restores them only in
  //    place, over the live volume.
  // 2. An hourly logical backup that can be restored anywhere: the cron service db-backup runs pg_dump against
  //    the private database and writes it to its own private bucket, db-backups (not uploads: other
  //    credentials), keeping 7 days (tools/backup/hourly_dump.sh). The weekly GitHub workflow restore-drill.yml
  //    restores the newest one into a throwaway database and checks it. RPO 1 hour.
  const dbBackups = bucket("db-backups", { region: "sjc" });
  const dbBackup = service("db-backup", {
    source: src(),
    build: { builder: "DOCKERFILE", dockerfilePath: "infra/railway/db-backup.Dockerfile",
             watchPatterns: ["infra/railway/db-backup.Dockerfile", "tools/backup/hourly_dump.sh"] },
    // Every hour at :07; the container backs up, prunes and exits (cron services must exit).
    deploy: { cronSchedule: "7 * * * *", restartPolicyType: "NEVER", ...cap(0.5, 0.5) },
    env: {
      PGHOST: "postgres.railway.internal",
      PGPORT: "5432",
      PGUSER: "${{postgres.POSTGRES_USER}}",
      PGPASSWORD: "${{postgres.POSTGRES_PASSWORD}}",
      PGDATABASE: "${{postgres.POSTGRES_DB}}",
      BACKUP_PREFIX: appEnv,
      KEEP_DAYS: "7",
      BACKUP_BUCKET: preserve(), // db-backups' bucketName
      AWS_ENDPOINT_URL: preserve(), // its endpoint
      AWS_REGION: preserve(), // its region
      AWS_ACCESS_KEY_ID: preserve(), // sealed
      AWS_SECRET_ACCESS_KEY: preserve(), // sealed
    },
  });

  // ── Web and admin (Next.js, infra/docker/next-app.Dockerfile) ──────────
  // NEXT_PUBLIC_* are baked into the browser bundle at build time (Dockerfile
  // ARGs), so they point at the public domains. Outside production the two
  // frontends sleep when idle (Railway "Serverless"); the backends don't: they
  // run timers (dispatch, outbox, sweeps) that must keep going.
  // Health check: a page that answers 200 without signing in (admin's / redirects).
  const next = (name: string, pkg: string, dir: string, healthcheck: string, extra: Env) =>
    service(name, {
      source: src(),
      build: { builder: "DOCKERFILE", dockerfilePath: "infra/docker/next-app.Dockerfile",
               watchPatterns: [`${dir}/**`, "packages/**", "pnpm-lock.yaml", "infra/docker/next-app.Dockerfile"] },
      healthcheck,
      healthcheckTimeout: 120,
      deploy: { ...(prod ? {} : { sleepApplication: true }), ...cap(0.5, 0.5) },
      env: {
        APP: pkg, APP_DIR: dir, PORT: "3000",
        // production only is indexable (robots.txt, meta and X-Robots-Tag); a build arg too
        APP_ENV: appEnv,
        CORE_API_URL: "http://core-api.railway.internal:8001",
        REALTIME_URL: "http://realtime.railway.internal:8004",
        NEXT_PUBLIC_CORE_URL: publicUrl("core-api"),
        NEXT_PUBLIC_REALTIME_URL: publicUrl("realtime"),
        // Error reports from the browser (Sentry; R19). A build arg: empty = off.
        ...(prod ? { NEXT_PUBLIC_SENTRY_DSN: preserve() } : {}),
        ...extra,
      },
    });

  const web = next("web", "@bhojango/web", "apps/web", "/", {
    CORE_API_INTERNAL_URL: "http://core-api.railway.internal:8001",
    NEXT_PUBLIC_APP_URL: prod ? preserve() : publicUrl("web"), // canonical links and the sitemap; production: by hand
    // Production pays through Stripe (a build arg; unset = the fake one, which production refuses: lib/payments.ts).
    ...(prod ? { NEXT_PUBLIC_PAYMENTS_PROVIDER: "stripe" } : {}),
  });
  const admin = next("admin", "@bhojango/admin", "apps/admin", "/login", {});

  return project("bhojango", {
    environments: ["QA", "staging", "production"],
    resources: [
      group("Data", [postgres, pgData, cache, dbBackup, dbBackups]),
      group("Backend", [coreApi, realtime, worker, uploads]),
      group("Frontends", [web, admin]),
    ],
  });
});
