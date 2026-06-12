/**
 * Route definitions for the Batch Engine API.
 */

import { Router } from "express";
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

// Order pool (admin/ops + internal callers presenting a service token)
router.post("/pool", requireRole(...ADMIN_ROLES), validate(validateAddToPool), addToPool);

// Batch operations
router.get("/pending", requireRole(...ADMIN_ROLES), getPendingBatches);
router.get("/:batchId", getBatch);
router.post("/:batchId/accept", validate(validateAcceptBatch), acceptBatch);
router.post("/:batchId/stops/:seq/complete", validate(validateCompleteStop), completeStop);
router.post("/:batchId/orders/:orderId/remove", validate(validateRemoveOrder), removeOrder);

// Engine admin
router.post("/engine/cycle", requireRole(...ADMIN_ROLES), triggerCycle);

export default router;
