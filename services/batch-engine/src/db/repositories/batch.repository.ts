/**
 * Batch Repository — database access for batches, batch orders, route stops.
 */

import { pool } from "../connection";
import { Batch, BatchOrder, RouteStop, BatchStatus, BatchCandidate } from "../../types";
import { logger } from "../../utils/logger";

export class BatchRepository {
  /**
   * Create a batch from a scored candidate.
   * Inserts into batches, batch_orders, and route_stops in a transaction.
   */
  async createFromCandidate(candidate: BatchCandidate): Promise<string> {
    const client = await pool.connect();
    try {
      await client.query("BEGIN");

      // Insert batch
      const batchResult = await client.query(
        `INSERT INTO batch_engine.batches
          (status, score, estimated_total_distance_km,
           estimated_total_time_min, max_detour_min, savings_percent)
         VALUES ('pending', $1, $2, $3, $4, $5)
         RETURNING id`,
        [
          candidate.score,
          candidate.totalDistanceKm,
          candidate.totalTimeMin,
          candidate.maxDetourMin,
          candidate.savingsPercent,
        ]
      );
      const batchId = batchResult.rows[0].id;

      // Insert batch orders
      for (let i = 0; i < candidate.orders.length; i++) {
        const order = candidate.orders[i];
        // Find the pickup and delivery stops for this order
        const pickupStop = candidate.route.find(
          (s) => s.orderId === order.orderId && s.type === "pickup"
        );
        const deliveryStop = candidate.route.find(
          (s) => s.orderId === order.orderId && s.type === "delivery"
        );

        await client.query(
          `INSERT INTO batch_engine.batch_orders
            (batch_id, order_id, pool_order_id, sequence,
             estimated_pickup_at, estimated_delivery_at, detour_minutes)
           VALUES ($1, $2, $3, $4, $5, $6, $7)`,
          [
            batchId,
            order.orderId,
            order.id,
            i + 1,
            pickupStop?.estimatedArrivalAt ?? new Date(),
            deliveryStop?.estimatedArrivalAt ?? new Date(),
            0, // detour computed separately
          ]
        );
      }

      // Insert route stops
      for (const stop of candidate.route) {
        await client.query(
          `INSERT INTO batch_engine.route_stops
            (batch_id, sequence, stop_type, order_id,
             lat, lng, estimated_arrival_at, estimated_dwell_min)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
          [
            batchId,
            stop.sequence,
            stop.type,
            stop.orderId,
            stop.point.lat,
            stop.point.lng,
            stop.estimatedArrivalAt,
            stop.estimatedDwellMin,
          ]
        );
      }

      // Log the event
      await client.query(
        `INSERT INTO batch_engine.batch_events
          (batch_id, event_type, metadata)
         VALUES ($1, 'batch.formed', $2)`,
        [
          batchId,
          JSON.stringify({
            orderCount: candidate.orders.length,
            score: candidate.score,
            savingsPercent: candidate.savingsPercent,
          }),
        ]
      );

      await client.query("COMMIT");
      return batchId;
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }

  /**
   * Get a batch with its orders and route stops.
   */
  async getById(batchId: string): Promise<Batch | null> {
    const batchResult = await pool.query(
      `SELECT * FROM batch_engine.batches WHERE id = $1`,
      [batchId]
    );
    if (batchResult.rows.length === 0) return null;

    const ordersResult = await pool.query(
      `SELECT * FROM batch_engine.batch_orders
       WHERE batch_id = $1 ORDER BY sequence`,
      [batchId]
    );

    const routeResult = await pool.query(
      `SELECT * FROM batch_engine.route_stops
       WHERE batch_id = $1 ORDER BY sequence`,
      [batchId]
    );

    return this.mapBatch(
      batchResult.rows[0],
      ordersResult.rows,
      routeResult.rows
    );
  }

  /**
   * Assign a driver to a batch.
   */
  async assignDriver(batchId: string, driverId: string): Promise<void> {
    const client = await pool.connect();
    try {
      await client.query("BEGIN");

      await client.query(
        `UPDATE batch_engine.batches
         SET driver_id = $1, status = 'assigned', assigned_at = now()
         WHERE id = $2`,
        [driverId, batchId]
      );

      await client.query(
        `INSERT INTO batch_engine.batch_events
          (batch_id, event_type, driver_id, metadata)
         VALUES ($1, 'batch.assigned', $2, '{}')`,
        [batchId, driverId]
      );

      await client.query("COMMIT");
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }

  /**
   * Update batch status.
   */
  async updateStatus(batchId: string, status: BatchStatus): Promise<void> {
    const extra = status === "completed" ? ", completed_at = now()" : "";
    await pool.query(
      `UPDATE batch_engine.batches SET status = $1 ${extra} WHERE id = $2`,
      [status, batchId]
    );
  }

  /**
   * Mark a specific order in a batch as picked up or delivered.
   */
  async updateBatchOrderStatus(
    batchId: string,
    orderId: string,
    status: "picked_up" | "delivered" | "cancelled",
    timestamp: Date
  ): Promise<void> {
    const timeCol = status === "picked_up" ? "actual_pickup_at" : "actual_delivery_at";
    await pool.query(
      `UPDATE batch_engine.batch_orders
       SET status = $1, ${timeCol} = $2
       WHERE batch_id = $3 AND order_id = $4`,
      [status, timestamp, batchId, orderId]
    );
  }

  /**
   * Remove an order from a batch (cancellation).
   * Returns the count of remaining orders.
   */
  async removeOrder(batchId: string, orderId: string): Promise<number> {
    const client = await pool.connect();
    try {
      await client.query("BEGIN");

      await client.query(
        `UPDATE batch_engine.batch_orders SET status = 'cancelled'
         WHERE batch_id = $1 AND order_id = $2`,
        [batchId, orderId]
      );

      await client.query(
        `DELETE FROM batch_engine.route_stops
         WHERE batch_id = $1 AND order_id = $2`,
        [batchId, orderId]
      );

      await client.query(
        `INSERT INTO batch_engine.batch_events
          (batch_id, event_type, order_id, metadata)
         VALUES ($1, 'batch.order_removed', $2, '{}')`,
        [batchId, orderId]
      );

      const remaining = await client.query(
        `SELECT COUNT(*) as cnt FROM batch_engine.batch_orders
         WHERE batch_id = $1 AND status != 'cancelled'`,
        [batchId]
      );

      await client.query("COMMIT");
      return parseInt(remaining.rows[0].cnt);
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }

  /**
   * Get pending batches (not yet assigned to a driver).
   */
  async getPending(): Promise<Batch[]> {
    const result = await pool.query(
      `SELECT b.*,
              json_agg(DISTINCT jsonb_build_object(
                'order_id', bo.order_id, 'sequence', bo.sequence,
                'status', bo.status, 'detour_minutes', bo.detour_minutes
              )) as orders_json
       FROM batch_engine.batches b
       JOIN batch_engine.batch_orders bo ON bo.batch_id = b.id
       WHERE b.status = 'pending'
       GROUP BY b.id
       ORDER BY b.score DESC`
    );
    return result.rows.map((row) => this.mapBatchSummary(row));
  }

  // ── Row mappers ─────────────────────────────────────────────────────────

  private mapBatch(batchRow: any, orderRows: any[], routeRows: any[]): Batch {
    return {
      id: batchRow.id,
      driverId: batchRow.driver_id,
      status: batchRow.status,
      score: batchRow.score,
      estimatedTotalDistanceKm: batchRow.estimated_total_distance_km,
      estimatedTotalTimeMin: batchRow.estimated_total_time_min,
      maxDetourMin: batchRow.max_detour_min,
      savingsPercent: batchRow.savings_percent,
      orders: orderRows.map((r) => ({
        orderId: r.order_id,
        poolOrderId: r.pool_order_id,
        sequence: r.sequence,
        estimatedPickupAt: new Date(r.estimated_pickup_at),
        estimatedDeliveryAt: new Date(r.estimated_delivery_at),
        actualPickupAt: r.actual_pickup_at ? new Date(r.actual_pickup_at) : null,
        actualDeliveryAt: r.actual_delivery_at ? new Date(r.actual_delivery_at) : null,
        detourMinutes: r.detour_minutes,
        status: r.status,
      })),
      route: routeRows.map((r) => ({
        sequence: r.sequence,
        type: r.stop_type,
        orderId: r.order_id,
        point: { lat: r.lat, lng: r.lng },
        estimatedArrivalAt: new Date(r.estimated_arrival_at),
        estimatedDwellMin: r.estimated_dwell_min,
      })),
      createdAt: new Date(batchRow.created_at),
      assignedAt: batchRow.assigned_at ? new Date(batchRow.assigned_at) : null,
      completedAt: batchRow.completed_at ? new Date(batchRow.completed_at) : null,
    };
  }

  private mapBatchSummary(row: any): Batch {
    return {
      id: row.id,
      driverId: row.driver_id,
      status: row.status,
      score: row.score,
      estimatedTotalDistanceKm: row.estimated_total_distance_km,
      estimatedTotalTimeMin: row.estimated_total_time_min,
      maxDetourMin: row.max_detour_min,
      savingsPercent: row.savings_percent,
      orders: [],
      route: [],
      createdAt: new Date(row.created_at),
      assignedAt: row.assigned_at ? new Date(row.assigned_at) : null,
      completedAt: null,
    };
  }
}
