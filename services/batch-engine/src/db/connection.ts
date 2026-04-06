/**
 * Database connection pool using node-postgres (pg).
 * All queries go through this pool. Repositories call pool.query().
 */

import { Pool, PoolConfig } from "pg";
import { DB_CONFIG } from "../config";
import { logger } from "../utils/logger";

const poolConfig: PoolConfig = {
  connectionString: DB_CONFIG.connectionString,
  min: DB_CONFIG.poolMin,
  max: DB_CONFIG.poolMax,
  idleTimeoutMillis: DB_CONFIG.idleTimeoutMs,
};

export const pool = new Pool(poolConfig);

pool.on("error", (err) => {
  logger.error("Unexpected pool error", { error: err.message });
});

/**
 * Run the migration SQL file against the database.
 * In production, use a proper migration tool (e.g., node-pg-migrate).
 */
export async function runMigrations(): Promise<void> {
  const fs = await import("fs");
  const path = await import("path");
  const migrationPath = path.join(__dirname, "migrations", "001_create_batch_tables.sql");
  const sql = fs.readFileSync(migrationPath, "utf-8");

  try {
    await pool.query(sql);
    logger.info("Database migrations applied successfully");
  } catch (err: unknown) {
    // Schema/tables may already exist — that's fine
    const message = err instanceof Error ? err.message : String(err);
    if (message.includes("already exists")) {
      logger.info("Database schema already up to date");
    } else {
      throw err;
    }
  }
}

export async function healthCheck(): Promise<boolean> {
  try {
    await pool.query("SELECT 1");
    return true;
  } catch {
    return false;
  }
}
