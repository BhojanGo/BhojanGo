/**
 * Route definitions for the Batch Engine API.
 */

import { NextFunction, Request, Response, Router } from "express";
import { SHADOW_MODE } from "../config";
import {
  addToPool,
  getBatch,
  acceptBatch,
  completeStop,
  removeOrder,
  triggerCycle,
  getPendingBatches,
} from "./batch.controller";
import {
  validate,
  validateAddToPool,
  validateAcceptBatch,
  validateCompleteStop,
  validateRemoveOrder,
} from "./middleware/validation";
import { authenticate, requireRole } from "./middleware/auth";

const router = Router();

// Every batch route requires a valid access token.
router.use(authenticate);

const ADMIN_ROLES = ["admin", "super_admin", "city_manager"];

// Shadow mode: batches are scored and visible to ops, but nobody delivers one.
function liveOnly(_req: Request, res: Response, next: NextFunction): void {
  if (SHADOW_MODE) {
    res.status(409).json({ error: "SHADOW_MODE", message: "Batching runs in shadow mode; batches can't be accepted" });
    return;
  }
  next();
}

// Order pool (admin/ops + internal callers presenting a service token)
router.post("/pool", requireRole(...ADMIN_ROLES), validate(validateAddToPool), addToPool);

// Batch operations
router.get("/pending", requireRole(...ADMIN_ROLES), getPendingBatches);
router.get("/:batchId", getBatch);
router.post("/:batchId/accept", liveOnly, validate(validateAcceptBatch), acceptBatch);
router.post("/:batchId/stops/:seq/complete", liveOnly, validate(validateCompleteStop), completeStop);
router.post("/:batchId/orders/:orderId/remove", liveOnly, validate(validateRemoveOrder), removeOrder);

// Engine admin
router.post("/engine/cycle", requireRole(...ADMIN_ROLES), triggerCycle);

export default router;
