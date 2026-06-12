/**
 * Batch Delivery Engine — Application Entry Point
 *
 * Starts:
 *   1. Express HTTP server (API + health check)
 *   2. Batch engine cycle timer (every N seconds)
 *   3. SQS event consumer (order.confirmed, order.cancelled)
 */

import express from "express";
import cors from "cors";
import { APP_CONFIG, ENGINE_CONFIG, JWT_CONFIG } from "./config";
import { runMigrations, healthCheck as dbHealthCheck } from "./db/connection";
import batchRoutes from "./api/routes";
import { startEngine, stopEngine } from "./api/batch.controller";
import { startConsumer } from "./events/consumer";
import { logger } from "./utils/logger";

const app = express();

// ── Middleware ───────────────────────────────────────────────────────────────

app.use(cors());
app.use(express.json());

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => {
    if (req.path !== "/health") {
      logger.info("HTTP request", {
        method: req.method,
        path: req.path,
        status: res.statusCode,
        durationMs: Date.now() - start,
      });
    }
  });
  next();
});

// ── Routes ──────────────────────────────────────────────────────────────────

app.use("/api/v1/batch", batchRoutes);

// ── Health Check ────────────────────────────────────────────────────────────

app.get("/health", async (_req, res) => {
  const dbOk = await dbHealthCheck();
  const status = dbOk ? "healthy" : "degraded";

  res.status(dbOk ? 200 : 503).json({
    status,
    service: APP_CONFIG.serviceName,
    version: APP_CONFIG.version,
    uptime: process.uptime(),
    checks: {
      database: dbOk ? "ok" : "fail",
      engine: "running",
    },
    config: {
      batchCycleSeconds: ENGINE_CONFIG.batchCycleSeconds,
      maxOrdersPerBatch: ENGINE_CONFIG.maxOrdersPerBatch,
      maxPickupRadiusKm: ENGINE_CONFIG.maxPickupRadiusKm,
      maxDetourMinutes: ENGINE_CONFIG.maxDetourMinutes,
    },
    timestamp: new Date().toISOString(),
  });
});

// ── Startup ─────────────────────────────────────────────────────────────────

async function start(): Promise<void> {
  try {
    // Fail fast: never run in production with the placeholder JWT secret (auth would be trivially forgeable).
    if (APP_CONFIG.env === "production" && JWT_CONFIG.usingDefaultSecret) {
      throw new Error("JWT_SECRET must be set in production (refusing to start with the default secret)");
    }

    // Run database migrations
    await runMigrations();
    logger.info("Database ready");

    // Start the HTTP server
    app.listen(APP_CONFIG.port, () => {
      logger.info(`Batch engine listening on port ${APP_CONFIG.port}`, {
        env: APP_CONFIG.env,
        version: APP_CONFIG.version,
      });
    });

    // Start the batch engine cycle
    startEngine();

    // Start SQS consumer (non-blocking — runs in background)
    startConsumer().catch((err) => {
      logger.error("SQS consumer crashed", {
        error: err instanceof Error ? err.message : String(err),
      });
    });

    // Graceful shutdown
    const shutdown = async () => {
      logger.info("Shutting down batch engine...");
      stopEngine();
      process.exit(0);
    };

    process.on("SIGTERM", shutdown);
    process.on("SIGINT", shutdown);
  } catch (err) {
    logger.error("Failed to start batch engine", {
      error: err instanceof Error ? err.message : String(err),
    });
    process.exit(1);
  }
}

start();
