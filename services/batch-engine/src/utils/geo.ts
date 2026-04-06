/**
 * Geo utilities — distance and time calculations.
 *
 * Uses the Haversine formula for straight-line distance, then applies
 * a city driving factor (1.4x) to approximate road distance.
 * For production at scale, swap this with Google Routes API or OSRM.
 */

import { GeoPoint } from "../types";
import { ENGINE_CONFIG } from "../config";

const EARTH_RADIUS_KM = 6371;
const CITY_DRIVING_FACTOR = 1.4; // roads aren't straight lines

/**
 * Haversine distance between two points (km).
 */
export function haversineKm(a: GeoPoint, b: GeoPoint): number {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h =
    sinLat * sinLat +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * sinLng * sinLng;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

/**
 * Estimated road distance (km) — haversine * city factor.
 */
export function roadDistanceKm(a: GeoPoint, b: GeoPoint): number {
  return haversineKm(a, b) * CITY_DRIVING_FACTOR;
}

/**
 * Estimated driving time (minutes) based on average speed.
 */
export function driveTimeMin(a: GeoPoint, b: GeoPoint): number {
  const km = roadDistanceKm(a, b);
  return (km / ENGINE_CONFIG.averageSpeedKmh) * 60;
}

/**
 * Total route distance: sum of consecutive leg distances.
 */
export function routeDistanceKm(points: GeoPoint[]): number {
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    total += roadDistanceKm(points[i - 1], points[i]);
  }
  return total;
}

/**
 * Total route time including driving + dwell at each stop.
 */
export function routeTimeMin(
  points: GeoPoint[],
  dwellMinPerStop: number
): number {
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    total += driveTimeMin(points[i - 1], points[i]);
    total += dwellMinPerStop;
  }
  return total;
}

/**
 * Check if two points are within a given radius.
 */
export function isWithinRadius(
  a: GeoPoint,
  b: GeoPoint,
  radiusKm: number
): boolean {
  return haversineKm(a, b) <= radiusKm;
}

/**
 * Find the centroid of a set of points.
 */
export function centroid(points: GeoPoint[]): GeoPoint {
  const n = points.length;
  if (n === 0) return { lat: 0, lng: 0 };
  const sum = points.reduce(
    (acc, p) => ({ lat: acc.lat + p.lat, lng: acc.lng + p.lng }),
    { lat: 0, lng: 0 }
  );
  return { lat: sum.lat / n, lng: sum.lng / n };
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}
