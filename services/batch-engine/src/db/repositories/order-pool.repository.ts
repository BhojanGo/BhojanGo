/**
 * Order Pool Repository — database access for the order pool.
 * All SQL queries for pool operations live here.
 */

import { pool } from "../connection";
import { PoolOrder, PoolStatus, GeoPoint } from "../../types";
import { logger } from "../../utils/logger";

export class OrderPoolRepository {
  /**
   * Insert a new order into the pool.
   */
  async insert(order: Omit<PoolOrder, "id" | "createdAt" | "status" | "batchId">): Promise<PoolOrder> {
    const result = await pool.query(
      `INSERT INTO batch_engine.order_pool
        (order_id, restaurant_id, restaurant_name,
         pickup_lat, pickup_lng, delivery_lat, delivery_lng,
         prep_ready_at, promised_delivery_at, priority,
         item_count, estimated_size_liters, currency, delivery_fee)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
       RETURNING *`,
      [
        order.orderId, order.restaurantId, order.restaurantName,
        order.pickupPoint.lat, order.pickupPoint.lng,
        order.deliveryPoint.lat, order.deliveryPoint.lng,
        order.prepReadyAt, order.promisedDeliveryAt, order.priority,
        order.itemCount, order.estimatedSizeLiters,
        order.currency, order.deliveryFee,
      ]
    );

    return this.mapRow(result.rows[0]);
  }

  /**
   * Get all orders currently waiting for batch assignment.
   */
  async getWaiting(): Promise<PoolOrder[]> {
    const result = await pool.query(
      `SELECT * FROM batch_engine.order_pool
       WHERE status = 'waiting'
       ORDER BY created_at ASC`
    );
    return result.rows.map(this.mapRow);
  }

  /**
   * Mark orders as batched and link to batch_id.
   */
  async markBatched(orderIds: string[], batchId: string): Promise<void> {
    await pool.query(
      `UPDATE batch_engine.order_pool
       SET status = 'batched', batch_id = $1
       WHERE order_id = ANY($2)`,
      [batchId, orderIds]
    );
  }

  /**
   * Mark orders as expired (exceeded max wait time).
   */
  async markExpired(orderIds: string[]): Promise<void> {
    if (orderIds.length === 0) return;
    await pool.query(
      `UPDATE batch_engine.order_pool
       SET status = 'expired'
       WHERE order_id = ANY($1)`,
      [orderIds]
    );
  }

  /**
   * Cancel an order in the pool (customer or restaurant cancelled).
   */
  async cancel(orderId: string): Promise<PoolOrder | null> {
    const result = await pool.query(
      `UPDATE batch_engine.order_pool
       SET status = 'cancelled'
       WHERE order_id = $1
       RETURNING *`,
      [orderId]
    );
    return result.rows[0] ? this.mapRow(result.rows[0]) : null;
  }

  /**
   * Find a pool order by order_id.
   */
  async findByOrderId(orderId: string): Promise<PoolOrder | null> {
    const result = await pool.query(
      `SELECT * FROM batch_engine.order_pool WHERE order_id = $1`,
      [orderId]
    );
    return result.rows[0] ? this.mapRow(result.rows[0]) : null;
  }

  // ── Row mapper ──────────────────────────────────────────────────────────

  private mapRow(row: any): PoolOrder {
    return {
      id: row.id,
      orderId: row.order_id,
      restaurantId: row.restaurant_id,
      restaurantName: row.restaurant_name,
      pickupPoint: { lat: row.pickup_lat, lng: row.pickup_lng },
      deliveryPoint: { lat: row.delivery_lat, lng: row.delivery_lng },
      prepReadyAt: new Date(row.prep_ready_at),
      promisedDeliveryAt: new Date(row.promised_delivery_at),
      priority: row.priority,
      itemCount: row.item_count,
      estimatedSizeLiters: row.estimated_size_liters,
      currency: row.currency,
      deliveryFee: parseFloat(row.delivery_fee),
      createdAt: new Date(row.created_at),
      status: row.status,
      batchId: row.batch_id,
    };
  }
}
