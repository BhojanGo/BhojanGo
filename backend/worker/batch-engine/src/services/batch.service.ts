/**
 * Batch Service — orchestrates the engine, repositories, and events.
 *
 * This is the main business logic layer. Controllers call this service,
 * and it coordinates between:
 *   - OrderPoolRepository (DB reads)
 *   - BatchRepository (DB writes)
 *   - BatchBuilder (engine logic)
 *   - EventPublisher (SNS events)
 */

import { BatchRepository } from "../db/repositories/batch.repository";
import { OrderPoolRepository } from "../db/repositories/order-pool.repository";
import { runBatchCycle, CycleResult } from "../engine/batch-builder";
import { GeoPoint, PoolOrder, Batch } from "../types";
import { AddToPoolRequest, CycleResponse } from "../dto/batch.dto";
import { centroid } from "../utils/geo";
import { logger } from "../utils/logger";

export class BatchService {
  private batchRepo: BatchRepository;
  private poolRepo: OrderPoolRepository;
  private cycleTimer: NodeJS.Timeout | null = null;

  constructor() {
    this.batchRepo = new BatchRepository();
    this.poolRepo = new OrderPoolRepository();
  }

  // ── Pool Management ───────────────────────────────────────────────────────

  /**
   * Add an order to the batch pool.
   * Called when order-svc confirms an order is being prepared.
   */
  async addToPool(req: AddToPoolRequest): Promise<PoolOrder> {
    logger.info("Adding order to pool", { orderId: req.orderId });

    const poolOrder = await this.poolRepo.insert({
      orderId: req.orderId,
      restaurantId: req.restaurantId,
      restaurantName: req.restaurantName,
      pickupPoint: req.pickupPoint,
      deliveryPoint: req.deliveryPoint,
      prepReadyAt: new Date(req.prepReadyAt),
      promisedDeliveryAt: new Date(req.promisedDeliveryAt),
      priority: req.priority,
      itemCount: req.itemCount,
      estimatedSizeLiters: req.estimatedSizeLiters,
      currency: req.currency,
      deliveryFee: req.deliveryFee,
    });

    return poolOrder;
  }

  // ── Engine Cycle ──────────────────────────────────────────────────────────

  /**
   * Run one batch-formation cycle.
   * Can be triggered manually (admin) or by the scheduled timer.
   */
  async runCycle(): Promise<CycleResponse> {
    const waiting = await this.poolRepo.getWaiting();

    if (waiting.length === 0) {
      return { batchesFormed: 0, ordersMatched: 0, ordersExpired: 0, cycleTimeMs: 0 };
    }

    // Use centroid of waiting orders as approximate driver start
    // In production, this would query delivery-svc for nearest available drivers
    const driverStart = centroid(waiting.map((o) => o.pickupPoint));

    const result = runBatchCycle(waiting, driverStart);

    // Persist formed batches
    let ordersMatched = 0;
    for (const candidate of result.batches) {
      const batchId = await this.batchRepo.createFromCandidate(candidate);
      const orderIds = candidate.orders.map((o) => o.orderId);
      await this.poolRepo.markBatched(orderIds, batchId);
      ordersMatched += orderIds.length;

      logger.info("Batch formed", {
        batchId,
        orderCount: orderIds.length,
        score: candidate.score,
        savingsPercent: candidate.savingsPercent,
      });
    }

    // Mark expired orders
    if (result.expiredOrderIds.length > 0) {
      await this.poolRepo.markExpired(result.expiredOrderIds);
    }

    return {
      batchesFormed: result.batches.length,
      ordersMatched,
      ordersExpired: result.expiredOrderIds.length,
      cycleTimeMs: result.cycleTimeMs,
    };
  }

  /**
   * Start the periodic engine cycle.
   */
  startCycleTimer(intervalSeconds: number): void {
    if (this.cycleTimer) return;
    logger.info("Starting batch engine cycle timer", { intervalSeconds });

    this.cycleTimer = setInterval(async () => {
      try {
        await this.runCycle();
      } catch (err) {
        logger.error("Batch cycle failed", {
          error: err instanceof Error ? err.message : String(err),
        });
      }
    }, intervalSeconds * 1000);
  }

  /**
   * Stop the periodic engine cycle.
   */
  stopCycleTimer(): void {
    if (this.cycleTimer) {
      clearInterval(this.cycleTimer);
      this.cycleTimer = null;
      logger.info("Batch engine cycle timer stopped");
    }
  }

  // ── Batch Operations ──────────────────────────────────────────────────────

  /**
   * Get batch details by ID.
   */
  async getBatch(batchId: string): Promise<Batch | null> {
    return this.batchRepo.getById(batchId);
  }

  /**
   * Driver accepts a pending batch.
   */
  async acceptBatch(batchId: string, driverId: string): Promise<Batch | null> {
    const batch = await this.batchRepo.getById(batchId);
    if (!batch || batch.status !== "pending") {
      return null;
    }

    await this.batchRepo.assignDriver(batchId, driverId);

    logger.info("Batch assigned to driver", { batchId, driverId });

    return this.batchRepo.getById(batchId);
  }

  /**
   * Mark a route stop as complete (pickup or delivery done).
   */
  async completeStop(
    batchId: string,
    sequence: number,
    driverId: string,
    timestamp: Date
  ): Promise<Batch | null> {
    const batch = await this.batchRepo.getById(batchId);
    if (!batch || batch.driverId !== driverId) return null;

    const stop = batch.route.find((s) => s.sequence === sequence);
    if (!stop) return null;

    // Update the batch order status
    const newStatus = stop.type === "pickup" ? "picked_up" : "delivered";
    await this.batchRepo.updateBatchOrderStatus(
      batchId, stop.orderId, newStatus as any, timestamp
    );

    // If this was the last delivery, mark batch as completed
    if (stop.type === "delivery") {
      const updated = await this.batchRepo.getById(batchId);
      if (updated) {
        const allDelivered = updated.orders.every(
          (o) => o.status === "delivered" || o.status === "cancelled"
        );
        if (allDelivered) {
          await this.batchRepo.updateStatus(batchId, "completed");
          logger.info("Batch completed", { batchId });
        }
      }
    }

    // Transition batch to in_progress on first pickup
    if (stop.type === "pickup" && batch.status === "assigned") {
      await this.batchRepo.updateStatus(batchId, "in_progress");
    }

    return this.batchRepo.getById(batchId);
  }

  /**
   * Remove an order from a batch (cancellation mid-delivery).
   * If it was the last order, cancel the entire batch.
   */
  async removeOrderFromBatch(
    batchId: string,
    orderId: string,
    reason: string
  ): Promise<{ removed: boolean; batchCancelled: boolean }> {
    const remaining = await this.batchRepo.removeOrder(batchId, orderId);
    await this.poolRepo.cancel(orderId);

    logger.info("Order removed from batch", { batchId, orderId, reason, remainingOrders: remaining });

    if (remaining === 0) {
      await this.batchRepo.updateStatus(batchId, "failed");
      return { removed: true, batchCancelled: true };
    }

    // TODO: recalculate route with remaining orders
    return { removed: true, batchCancelled: false };
  }

  /**
   * Get all pending batches (for driver assignment).
   */
  async getPendingBatches(): Promise<Batch[]> {
    return this.batchRepo.getPending();
  }
}
