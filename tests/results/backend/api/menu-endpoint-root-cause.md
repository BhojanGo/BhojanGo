# Menu Endpoint Root Cause Analysis - IP.PR.01.010

**Issue:** Menu endpoint returns 500 INTERNAL_ERROR for valid restaurant UUIDs

## Scope Status

**IP.PR.01.010 — Document Menu Endpoint Failure Root Cause: PARTIAL**

- Symptom documented: **YES** — endpoint returns 500 for valid UUIDs
- Root cause confirmed: **NO** — stack trace not captured; handler-level cause unknown
- Fix applied: **NO** — deferred to SPR-02

## Endpoints Tested

### 1. Restaurant List - OK
```
GET http://localhost:8002/api/v1/restaurants
Status: 200
Response: Array of restaurant objects
```

### 2. Restaurant Detail - OK
```
GET http://localhost:8002/api/v1/restaurants/8e7f8732-2c53-48e7-8c8b-41cdca04a3f4
Status: 200
Response: Full restaurant object with all fields
```

### 3. Menu Endpoint - FAILS
```
GET http://localhost:8002/api/v1/restaurants/8e7f8732-2c53-48e7-8c8b-41cdca04a3f4/menu
Status: 500
Response: {
  "detail": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again."
  }
}
```

### 4. Auth Check - 404 (expected for unauthenticated)
```
GET http://localhost:8001/api/v1/me
Status: 404
Response: {"detail":"Not Found"}
```

## Root Cause Analysis (Preliminary)

**Status: SYMPTOM DOCUMENTED ONLY — ROOT CAUSE NOT CONFIRMED**

The menu endpoint returns `500 INTERNAL_ERROR` for every valid restaurant UUID tested.

**Observed behavior:**
- No meaningful error detail in response body
- Response time ~1.6s suggests a DB query or external call fails before returning

**Likely causes (requires stack trace to confirm):**
1. OpenSearch connection failure — restaurant-svc tries to query OpenSearch index and crashes
2. Missing DB fallback — no fallback from OpenSearch to `menu_categories` + `menu_items` tables
3. SQL join error in menu query
4. Unhandled exception in route handler

**Next step for SPR-02:**
Enable debug logging on restaurant-svc and capture the full stack trace from the menu endpoint handler (`app/api/v1/restaurants.py`).

## Impact

- **Frontend Blank Page**: Restaurant detail pages (`/restaurants/[id]`) return HTML shell but menu section will be empty or show error
- **User Experience**: Users cannot view restaurant menus, effectively making the app unusable for ordering
- **SPR-01**: This is likely the root cause of reported blank page issues on restaurant detail routes

## Next Steps (SPR-02)

1. Capture restaurant-svc stack trace for the menu endpoint
2. Implement DB fallback for menu search if OpenSearch is unavailable
3. Add proper error handling in menu route handler

## Test Restaurant UUID
Use this UUID for testing: `8e7f8732-2c53-48e7-8c8b-41cdca04a3f4` (Dunkin' Donuts)