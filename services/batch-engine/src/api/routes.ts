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

const router = Router();

// Order pool
router.post("/pool", validate(validateAddToPool), addToPool);

// Batch operations
router.get("/pending", getPendingBatches);
router.get("/:batchId", getBatch);
router.post("/:batchId/accept", validate(validateAcceptBatch), acceptBatch);
router.post("/:batchId/stops/:seq/complete", validate(validateCompleteStop), completeStop);
router.post("/:batchId/orders/:orderId/remove", validate(validateRemoveOrder), removeOrder);

// Engine admin
router.post("/engine/cycle", triggerCycle);

export default router;
