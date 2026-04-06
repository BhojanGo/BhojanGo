/**
 * Batch Controller — HTTP handlers for the Batch Engine API.
 *
 * Endpoints:
 *   POST /api/v1/batch/pool             Add order to pool
 *   GET  /api/v1/batch/:batchId         Get batch details
 *   POST /api/v1/batch/:batchId/accept  Driver accepts batch
 *   POST /api/v1/batch/:batchId/stops/:seq/complete  Mark stop done
 *   POST /api/v1/batch/:batchId/orders/:orderId/remove  Remove order
 *   POST /api/v1/batch/engine/cycle     Manually trigger cycle (admin)
 *   GET  /api/v1/batch/pending          List pending batches for drivers
 */

import { Request, Response } from "express";
import { BatchService } from "../services/batch.service";
import { ENGINE_CONFIG } from "../config";
import { ApiResponse } from "../dto/batch.dto";

const batchService = new BatchService();

function success<T>(res: Response, data: T, status = 200): void {
  const body: ApiResponse<T> = {
    success: true,
    data,
    timestamp: new Date().toISOString(),
  };
  res.status(status).json(body);
}

function error(res: Response, message: string, status = 500): void {
  res.status(status).json({
    success: false,
    error: message,
    timestamp: new Date().toISOString(),
  });
}

// ── POST /api/v1/batch/pool ─────────────────────────────────────────────────

export async function addToPool(req: Request, res: Response): Promise<void> {
  try {
    const poolOrder = await batchService.addToPool(req.body);
    success(res, {
      poolOrderId: poolOrder.id,
      status: poolOrder.status,
      estimatedBatchWindow: `~${ENGINE_CONFIG.batchCycleSeconds} seconds`,
    }, 201);
  } catch (err: any) {
    if (err.message?.includes("duplicate key")) {
      error(res, "Order already in pool", 409);
    } else {
      error(res, err.message);
    }
  }
}

// ── GET /api/v1/batch/:batchId ──────────────────────────────────────────────

export async function getBatch(req: Request, res: Response): Promise<void> {
  try {
    const batch = await batchService.getBatch(req.params.batchId);
    if (!batch) {
      error(res, "Batch not found", 404);
      return;
    }

    success(res, {
      id: batch.id,
      driverId: batch.driverId,
      status: batch.status,
      score: batch.score,
      estimatedTotalDistanceKm: batch.estimatedTotalDistanceKm,
      estimatedTotalTimeMin: batch.estimatedTotalTimeMin,
      maxDetourMin: batch.maxDetourMin,
      savingsPercent: batch.savingsPercent,
      orders: batch.orders.map((o) => ({
        orderId: o.orderId,
        sequence: o.sequence,
        estimatedPickupAt: o.estimatedPickupAt.toISOString(),
        estimatedDeliveryAt: o.estimatedDeliveryAt.toISOString(),
        detourMinutes: o.detourMinutes,
        status: o.status,
      })),
      route: batch.route.map((s) => ({
        sequence: s.sequence,
        type: s.type,
        orderId: s.orderId,
        point: s.point,
        estimatedArrivalAt: s.estimatedArrivalAt.toISOString(),
        estimatedDwellMin: s.estimatedDwellMin,
      })),
      createdAt: batch.createdAt.toISOString(),
      assignedAt: batch.assignedAt?.toISOString() ?? null,
      completedAt: batch.completedAt?.toISOString() ?? null,
    });
  } catch (err: any) {
    error(res, err.message);
  }
}

// ── POST /api/v1/batch/:batchId/accept ──────────────────────────────────────

export async function acceptBatch(req: Request, res: Response): Promise<void> {
  try {
    const batch = await batchService.acceptBatch(
      req.params.batchId,
      req.body.driverId
    );
    if (!batch) {
      error(res, "Batch not found or not in pending status", 404);
      return;
    }

    success(res, {
      batchId: batch.id,
      status: batch.status,
      route: batch.route.map((s) => ({
        sequence: s.sequence,
        type: s.type,
        orderId: s.orderId,
        point: s.point,
        estimatedArrivalAt: s.estimatedArrivalAt.toISOString(),
        estimatedDwellMin: s.estimatedDwellMin,
      })),
      estimatedCompletionAt: new Date(
        Date.now() + batch.estimatedTotalTimeMin * 60_000
      ).toISOString(),
    });
  } catch (err: any) {
    error(res, err.message);
  }
}

// ── POST /api/v1/batch/:batchId/stops/:seq/complete ─────────────────────────

export async function completeStop(req: Request, res: Response): Promise<void> {
  try {
    const batch = await batchService.completeStop(
      req.params.batchId,
      parseInt(req.params.seq),
      req.body.driverId,
      req.body.timestamp ? new Date(req.body.timestamp) : new Date()
    );
    if (!batch) {
      error(res, "Batch or stop not found", 404);
      return;
    }
    success(res, { batchId: batch.id, status: batch.status });
  } catch (err: any) {
    error(res, err.message);
  }
}

// ── POST /api/v1/batch/:batchId/orders/:orderId/remove ──────────────────────

export async function removeOrder(req: Request, res: Response): Promise<void> {
  try {
    const result = await batchService.removeOrderFromBatch(
      req.params.batchId,
      req.params.orderId,
      req.body.reason
    );
    success(res, {
      batchId: req.params.batchId,
      orderId: req.params.orderId,
      removed: result.removed,
      batchCancelled: result.batchCancelled,
      routeRecalculated: !result.batchCancelled,
    });
  } catch (err: any) {
    error(res, err.message);
  }
}

// ── POST /api/v1/batch/engine/cycle ─────────────────────────────────────────

export async function triggerCycle(req: Request, res: Response): Promise<void> {
  try {
    const result = await batchService.runCycle();
    success(res, result);
  } catch (err: any) {
    error(res, err.message);
  }
}

// ── GET /api/v1/batch/pending ───────────────────────────────────────────────

export async function getPendingBatches(req: Request, res: Response): Promise<void> {
  try {
    const batches = await batchService.getPendingBatches();
    success(res, batches.map((b) => ({
      id: b.id,
      score: b.score,
      estimatedTotalDistanceKm: b.estimatedTotalDistanceKm,
      estimatedTotalTimeMin: b.estimatedTotalTimeMin,
      savingsPercent: b.savingsPercent,
      orderCount: b.orders.length,
      createdAt: b.createdAt.toISOString(),
    })));
  } catch (err: any) {
    error(res, err.message);
  }
}

/**
 * Start the batch engine cycle timer.
 * Called from main.ts at app startup.
 */
export function startEngine(): void {
  batchService.startCycleTimer(ENGINE_CONFIG.batchCycleSeconds);
}

export function stopEngine(): void {
  batchService.stopCycleTimer();
}
