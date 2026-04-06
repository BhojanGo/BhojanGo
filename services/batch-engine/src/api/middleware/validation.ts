/**
 * Request validation middleware.
 * Validates incoming JSON bodies against expected shapes.
 */

import { Request, Response, NextFunction } from "express";

type Validator = (body: any) => string | null;

/**
 * Express middleware factory: validates req.body and returns 400 on failure.
 */
export function validate(validator: Validator) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const error = validator(req.body);
    if (error) {
      res.status(400).json({
        success: false,
        error,
        timestamp: new Date().toISOString(),
      });
      return;
    }
    next();
  };
}

// ── Validators ──────────────────────────────────────────────────────────────

export function validateAddToPool(body: any): string | null {
  if (!body.orderId) return "orderId is required";
  if (!body.restaurantId) return "restaurantId is required";
  if (!body.restaurantName) return "restaurantName is required";
  if (!isValidGeoPoint(body.pickupPoint)) return "pickupPoint must have lat and lng";
  if (!isValidGeoPoint(body.deliveryPoint)) return "deliveryPoint must have lat and lng";
  if (!body.prepReadyAt) return "prepReadyAt is required (ISO 8601)";
  if (!body.promisedDeliveryAt) return "promisedDeliveryAt is required (ISO 8601)";
  if (isNaN(Date.parse(body.prepReadyAt))) return "prepReadyAt must be valid ISO 8601";
  if (isNaN(Date.parse(body.promisedDeliveryAt))) return "promisedDeliveryAt must be valid ISO 8601";
  if (body.priority && !["standard", "priority", "scheduled"].includes(body.priority)) {
    return "priority must be standard, priority, or scheduled";
  }
  if (body.currency && !["USD", "INR"].includes(body.currency)) {
    return "currency must be USD or INR";
  }
  return null;
}

export function validateAcceptBatch(body: any): string | null {
  if (!body.driverId) return "driverId is required";
  if (!isValidGeoPoint(body.currentLocation)) return "currentLocation must have lat and lng";
  return null;
}

export function validateCompleteStop(body: any): string | null {
  if (!body.driverId) return "driverId is required";
  if (!isValidGeoPoint(body.currentLocation)) return "currentLocation must have lat and lng";
  return null;
}

export function validateRemoveOrder(body: any): string | null {
  if (!body.reason) return "reason is required";
  if (!["customer_cancelled", "restaurant_cancelled", "admin_override"].includes(body.reason)) {
    return "reason must be customer_cancelled, restaurant_cancelled, or admin_override";
  }
  return null;
}

function isValidGeoPoint(point: any): boolean {
  return (
    point &&
    typeof point.lat === "number" &&
    typeof point.lng === "number" &&
    point.lat >= -90 && point.lat <= 90 &&
    point.lng >= -180 && point.lng <= 180
  );
}
