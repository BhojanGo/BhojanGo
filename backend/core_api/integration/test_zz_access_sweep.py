"""Access-control sweep: every core_api endpoint, three ways. (Named to run
last: if a hole lets a request through, it can't spoil the other tests' data.)

1. No token → refused (401/403), unless the route is deliberately public.
2. A signed-in user of the wrong kind (customer on a partner route, partner
   on an admin route, an admin without the permission) → refused.
3. Someone else's resource (another customer's order, another restaurant's
   menu, another rider's delivery, another city's or country's data) →
   refused (403/404, never 2xx and never a business error that means the
   check was passed).

Every route must have a policy in POLICY; a new endpoint without one fails
`test_every_route_has_a_policy`. Requests carry valid bodies, so a refusal
can't hide behind a validation error.
"""
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

REFUSED = {401, 403, 404}
NO_TOKEN = {401, 403}
ADMIN_PW = "BhojanGoAdmin1"

# Who plays which part. The resources below belong to the "own" side.
ACTORS = {
    "customer": ("customer1.hyd@example.com", "BhojanGo123"),          # owns the order
    "other_customer": ("customer2.hyd@example.com", "BhojanGo123"),
    "partner": ("partner.hyd@example.com", "BhojanGo123"),             # owns Spice Route
    "other_partner": ("partner.boi@example.com", "BhojanGo123"),
    "rider": ("rider1.hyd@example.com", "BhojanGo123"),                # delivered the order
    "other_rider": ("rider2.hyd@example.com", "BhojanGo123"),
    "ops_hyd": ("ops.hyd@example.com", ADMIN_PW),
    "ops_boi": ("ops.boi@example.com", ADMIN_PW),                      # another city
    "support_hyd": ("support.hyd@example.com", ADMIN_PW),
    "viewer": ("viewer@example.com", ADMIN_PW),                        # read-only everywhere
    "finance_in": ("finance.in@example.com", ADMIN_PW),
    "finance_us": ("finance.us@example.com", ADMIN_PW),                # another country
    "cm_in": ("cm.in@example.com", ADMIN_PW),
    "cm_us": ("cm.us@example.com", ADMIN_PW),
}
NOT_ADMINS = ["customer", "partner", "rider"]


@dataclass
class Policy:
    kind: str  # public | signed | user | admin
    refused: list[str] = field(default_factory=list)  # wrong role or someone else's resource
    body: Callable[["Ctx"], Any] | None = None
    params: Callable[["Ctx"], dict] | None = None
    why: str = ""


def public(why: str) -> Policy:
    return Policy("public", why=why)


def user(*refused: str, body=None, params=None) -> Policy:  # type: ignore[no-untyped-def]
    return Policy("user", list(refused), body, params)


def admin(*refused: str, body=None, params=None) -> Policy:  # type: ignore[no-untyped-def]
    return Policy("admin", NOT_ADMINS + list(refused), body, params)


# Bodies (valid, so a refusal isn't a validation error)
def _items(c: "Ctx") -> list[dict]:
    return [{"menu_item_id": c.item, "quantity": 1}]


ADDRESS = {"street": "Flat 1", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}
OPTION_GROUP = {"name": "Sweep extras", "min_picks": 0, "max_picks": 1, "options": [{"name": "Lemon", "price": 0}]}
MENU_ITEM = {"name": "Sweep item", "price": 10, "category": "Sweep"}
RESTAURANT = {
    "name": "Sweep Kitchen", "cuisine_types": ["Indian"], "currency": "INR", "country": "IN", "city": "Hyderabad",
    "address": {"street": "1 Sweep Rd", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"},
    "location": {"lat": 17.44, "lng": 78.39}, "delivery_time_min": 20, "delivery_time_max": 40,
    "minimum_order_amount": 0, "delivery_fee": 0,
}
HYD = {"country": "IN", "region": "IN-TG", "city": "IN-TG-HYD"}
POLYGON = {"type": "Polygon", "coordinates": [[[78.30, 17.40], [78.31, 17.40], [78.31, 17.41], [78.30, 17.40]]]}

R = "/api/v1/restaurants/{restaurant_id}"
POLICY: dict[tuple[str, str], Policy] = {
    # ── public by design ──────────────────────────────────────────────────────
    ("GET", "/.well-known/jwks.json"): public("public keys"),
    ("GET", "/api/v1/auth/jwks"): public("public keys"),
    ("GET", "/health"): public("probe"), ("GET", "/health/live"): public("probe"),
    ("GET", "/health/ready"): public("probe"), ("GET", "/metrics"): public("scraped inside the VPC"),
    **{("POST", f"/api/v1/auth/{p}"): public("signing in")
       for p in ("login", "phone", "refresh", "register", "reset-password", "send-otp", "social-login", "verify-otp")},
    ("POST", "/api/v1/finance/stripe/connect/webhook"): public("signature-checked webhook"),
    ("POST", "/api/v1/payments/fake/webhook"): public("signature-checked webhook"),
    ("POST", "/api/v1/payments/razorpay/webhook"): public("signature-checked webhook"),
    ("POST", "/api/v1/payments/stripe/webhook"): public("signature-checked webhook"),
    ("GET", "/api/v1/markets/locate"): public("does this address get delivery"),
    ("POST", "/api/v1/ops/alerts/webhook"): public("Alertmanager's webhook, token-checked (P23)"),
    ("GET", "/api/v1/markets/cities"): public("where we deliver: the web's city pages"),
    ("GET", "/api/v1/pricing/example"): public("the web home page's example bill, from the real engine"),
    ("GET", "/api/v1/restaurants/by-slug/{slug}"): public("browse: the web's restaurant pages"),
    ("POST", "/api/v1/markets/waitlist"): public("tell me when you launch, from outside served areas"),
    ("GET", "/api/v1/restaurants"): public("browse"), ("GET", "/api/v1/restaurants/search"): public("browse"),
    ("GET", R): public("browse"), ("GET", f"{R}/availability"): public("browse"),
    ("GET", f"{R}/delivery-check"): public("browse"), ("GET", f"{R}/hours"): public("browse"),
    ("GET", f"{R}/menu"): public("browse"), ("GET", f"{R}/option-groups"): public("browse"),
    # ── service to service ───────────────────────────────────────────────────
    ("GET", "/api/v1/internal/orders/{order_id}/dispatch"): Policy("signed"),
    ("POST", "/api/v1/internal/orders/{order_id}/assign-rider"): Policy("signed", body=lambda c: {"rider_id": c.rider_id}),
    ("GET", "/api/v1/internal/riders/{rider_id}/ready"): Policy("signed"),
    # ── signed-in, own data only (nothing in the path points at someone else) ─
    ("POST", "/api/v1/auth/logout"): user(), ("GET", "/api/v1/users/me"): user(),
    ("PATCH", "/api/v1/users/me"): user(body=lambda c: {}), ("PUT", "/api/v1/users/me"): user(body=lambda c: {}),
    ("DELETE", "/api/v1/users/me"): user(),
    ("GET", "/api/v1/me/addresses"): user(), ("POST", "/api/v1/me/addresses"): user(body=lambda c: {"street": "x", "city": "y"}),
    ("DELETE", "/api/v1/me/addresses/{address_id}"): user("other_customer"),
    ("GET", "/api/v1/wallet/balance"): user(), ("GET", "/api/v1/wallet/transactions"): user(),
    ("POST", "/api/v1/wallet/topup"): user(body=lambda c: {"amount": 1, "currency": "INR", "payment_method_id": "pm_x"}),
    ("POST", "/api/v1/pricing/quote"): user(body=lambda c: {"restaurant_id": c.spice, "items": _items(c),
                                                             "deliver_to": {"lat": 17.4483, "lng": 78.3915}}),
    ("GET", "/api/v1/pricing/quotes/{quote_id}"): user("other_customer"),
    ("GET", "/api/v1/orders"): user(),
    ("POST", "/api/v1/orders"): user(body=lambda c: {"restaurant_id": c.spice, "items": _items(c), "payment_method": "upi",
                                                     "quote_token": "x", "delivery_address": ADDRESS}),
    ("GET", "/api/v1/finance/payout-accounts/me"): user(), ("GET", "/api/v1/finance/statements/me"): user(),
    # self sign-up (B1): your own account only; admins use another number
    ("POST", "/api/v1/riders/apply"): user("ops_hyd", body=lambda c: {"full_name": "Sweep", "city_code": "IN-TG-HYD"}),
    ("POST", "/api/v1/restaurants/apply"): user("ops_hyd", body=lambda c: {
        "full_name": "Sweep", "kitchen_name": "Sweep", "city_code": "IN-TG-HYD", "street": "Road 1", "area": "Madhapur",
        "zip": "500081", "lat": 17.44, "lng": 78.39, "cuisines": ["Thali"]}),
    # riders only (P18)
    ("GET", "/api/v1/finance/earnings/me"): user("customer", "partner", "ops_hyd"),
    ("POST", "/api/v1/uploads"): user("ops_hyd"),  # riders, partners (P19) and customers (problem photos, B5); purpose checked per role
    ("GET", "/api/v1/riders/me/onboarding"): user("customer", "partner", "ops_hyd"),
    ("POST", "/api/v1/riders/me/documents"): user("customer", "partner", "ops_hyd",
                                                   body=lambda c: {"kind": "licence", "file_key": f"rider_document/{c.rider_id}/x.jpg"}),
    # a key another rider uploaded is refused even to a rider: see test_riders.py
    ("POST", "/api/v1/finance/payout-accounts"): user(
        "other_partner", "customer", body=lambda c: {"payee_type": "restaurant", "restaurant_id": c.spice}),
    # ── orders: the customer, the restaurant, the assigned rider, admins for the city ──
    ("GET", "/api/v1/orders/{order_id}"): user("other_customer", "other_partner", "other_rider", "ops_boi"),
    ("GET", "/api/v1/orders/{order_id}/breakdown"): user("other_customer", "other_partner", "other_rider", "ops_boi"),
    # report a problem (B5): the order's customer only
    ("POST", "/api/v1/orders/{order_id}/problems"): user("other_customer", "partner", "rider", "ops_hyd",
                                                        body=lambda c: {"items": [{"menu_item_id": c.item, "quantity": 1}], "reason": "quality"}),
    # call-back requests (B3): the kitchen's owner asks; admins see and resolve them in their city
    ("POST", f"{R}/callback"): user("other_partner", "customer", "rider", "ops_hyd", body=lambda c: {"topic": "other"}),
    ("GET", f"{R}/callback"): user("other_partner", "customer", "rider", "ops_hyd"),
    ("GET", "/api/v1/ops/tickets"): admin(),
    ("GET", "/api/v1/ops/alerts"): admin(),  # P23
    ("POST", "/api/v1/ops/tickets/{ticket_id}/resolve"): admin("ops_boi", "viewer", "finance_in", body=lambda c: {"resolution": "Sweep"}),
    # quick messages (B2): the order's customer and rider only; not the kitchen, not admins
    ("GET", "/api/v1/orders/{order_id}/messages"): user("other_customer", "other_partner", "other_rider", "partner", "ops_hyd"),
    ("POST", "/api/v1/orders/{order_id}/messages"): user("other_customer", "other_partner", "other_rider", "partner", "ops_hyd",
                                                         body=lambda c: {"preset": "outside"}),
    ("GET", "/api/v1/orders/{order_id}/timeline"): user("other_customer", "other_partner", "other_rider", "ops_boi"),
    ("POST", "/api/v1/orders/{order_id}/cancel"): user("other_customer", "other_partner", "other_rider", "ops_boi",
                                                       body=lambda c: {"reason": "customer_cancelled"}),
    ("PUT", "/api/v1/orders/{order_id}/status"): user("other_customer", "other_partner", "other_rider", "ops_boi",
                                                      body=lambda c: {"status": "delivered"}),
    ("GET", "/api/v1/orders/restaurant/{restaurant_id}"): user("customer", "other_partner", "rider", "ops_boi"),
    ("GET", "/api/v1/orders/driver/active"): user("customer", "partner"),
    ("GET", "/api/v1/orders/admin/pain-points"): admin("ops_boi"),
    ("GET", "/api/v1/payments/{order_id}"): user("other_customer", "other_partner", "other_rider", "ops_boi"),
    ("GET", "/api/v1/payments/orders/{order_id}/status"): user("other_customer", "other_partner", "other_rider"),
    ("GET", "/api/v1/payments/orders/{order_id}/refunds"): user("other_customer", "other_partner", "other_rider", "ops_boi"),
    ("POST", "/api/v1/payments/initiate"): user("other_customer", "other_partner", "other_rider",
                                                body=lambda c: {"order_id": c.order, "payment_method_type": "upi"}),
    ("POST", "/api/v1/payments/fake/{payment_intent_id}/complete"): user(
        "other_customer", "other_partner", "other_rider", body=lambda c: {"outcome": "succeeded"}),
    ("POST", "/api/v1/payments/razorpay/verify"): user("other_customer", body=lambda c: {
        "razorpay_order_id": c.intent_provider_id, "razorpay_payment_id": "pay_x", "razorpay_signature": "x"}),
    ("POST", "/api/v1/payments/orders/{order_id}/refunds"): admin("viewer", "ops_boi", "finance_us", body=lambda c: {
        "items": _items(c), "reason": "goodwill"}),
    ("GET", "/api/v1/pricing/orders/{order_id}/bill"): user("other_customer", "other_partner", "other_rider", "ops_boi"),
    ("GET", "/api/v1/pricing/orders/{order_id}/snapshot"): admin("ops_boi", "finance_us"),
    ("POST", "/api/v1/pricing/simulate"): admin("ops_boi", "cm_us", body=lambda c: {
        "city": "IN-TG-HYD", "cart": {"food_subtotal": "560"}, "distance": "4.2", "local_time": "2026-11-12T20:00:00"}),
    # ── restaurants: their owner or admins for the city ──────────────────────
    ("POST", "/api/v1/restaurants"): user("customer", "rider", body=lambda c: RESTAURANT),
    ("GET", "/api/v1/restaurants/admin/pending"): admin(),
    ("POST", "/api/v1/restaurants/licences/check"): admin("ops_boi"),
    ("PUT", R): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: {"description": "sweep"}),
    ("POST", f"{R}/approve"): admin("partner", "viewer", "ops_boi"),
    ("POST", f"{R}/reject"): admin("partner", "viewer", "ops_boi", params=lambda c: {"reason": "sweep"}),
    ("PUT", f"{R}/hours"): user("customer", "rider", "other_partner", "ops_boi",
                                body=lambda c: {"weekly": [{"weekday": 0, "opens": "09:00", "closes": "22:00"}]}),
    ("PUT", f"{R}/hours/overrides/{{day}}"): user("customer", "rider", "other_partner", "ops_boi",
                                                  body=lambda c: {"closed": True, "note": "sweep"}),
    ("DELETE", f"{R}/hours/overrides/{{day}}"): user("customer", "rider", "other_partner", "ops_boi"),
    ("PUT", f"{R}/licence"): user("customer", "rider", "other_partner", "ops_boi",
                                  body=lambda c: {"fssai_number": "12345678901234", "fssai_expires_on": "2030-01-01"}),
    ("PUT", f"{R}/prep-time"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: {"minutes": 25}),
    # partner tablet (P19)
    ("GET", "/api/v1/restaurants/mine"): user(),  # only ever your own
    ("GET", f"{R}/today"): user("customer", "rider", "other_partner", "ops_boi"),
    ("PUT", f"{R}/pause"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: {"paused": False}),
    ("PUT", f"{R}/busy"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: {"extra_minutes": 0}),
    ("GET", f"{R}/offers"): user("customer", "rider", "other_partner", "ops_boi"),
    ("POST", f"{R}/offers"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: {
        "template": "free_delivery", "name": "Sweep", "weekly_cap": "100"}),
    ("POST", f"{R}/offers/{{offer_id}}/end"): user("customer", "rider", "other_partner", "ops_boi"),
    ("GET", f"{R}/application"): user("customer", "rider", "other_partner", "ops_boi"),
    ("PUT", f"{R}/gst"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: {"gstin": "36AABCU9603R1ZM"}),
    ("PUT", f"{R}/pricing"): user("customer", "rider", "other_partner", "ops_boi",
                                  body=lambda c: {"pricing_model": "percentage_commission", "commission_rate": "0.15"}),
    ("POST", f"{R}/menu-items"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: MENU_ITEM),
    ("PUT", f"{R}/menu-items/{{item_id}}"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: {"price": 999}),
    ("DELETE", f"{R}/menu-items/{{item_id}}"): user("customer", "rider", "other_partner", "ops_boi"),
    ("PUT", f"{R}/menu-items/{{item_id}}/option-groups"): user("customer", "rider", "other_partner", "ops_boi",
                                                              body=lambda c: {"group_ids": []}),
    ("PUT", f"{R}/menu-items/{{item_id}}/sold-out"): user("customer", "rider", "other_partner", "ops_boi",
                                                         body=lambda c: {"sold_out": True}),
    ("POST", f"{R}/option-groups"): user("customer", "rider", "other_partner", "ops_boi", body=lambda c: OPTION_GROUP),
    ("PUT", f"{R}/option-groups/{{group_id}}"): user("customer", "rider", "other_partner", "ops_boi",
                                                     body=lambda c: OPTION_GROUP),
    ("DELETE", f"{R}/option-groups/{{group_id}}"): user("customer", "rider", "other_partner", "ops_boi"),
    ("POST", f"{R}/reviews"): user("other_customer", "partner", "rider",
                                   body=lambda c: {"order_id": c.order, "rating": 5, "comment": "sweep"}),
    # ── admin: rules, markets, audit, admins, users ──────────────────────────
    ("GET", "/api/v1/rules"): admin(params=lambda c: {"family": "customer_fee"}),
    ("POST", "/api/v1/rules"): admin("viewer", "ops_boi", "support_hyd", body=lambda c: {
        "family": "business", "template": "cancel_window", "params": {"minutes": 2},
        "scope_level": "city", "scope_id": "IN-TG-HYD"}),
    ("GET", "/api/v1/rules/approvals"): admin(), ("GET", "/api/v1/rules/templates"): admin(),
    ("GET", "/api/v1/rules/resolve"): admin(params=lambda c: HYD),
    ("GET", "/api/v1/rules/{rule_id}"): admin("ops_boi", "cm_us"),
    ("GET", "/api/v1/rules/{rule_id}/history"): admin("ops_boi", "cm_us"),
    ("PATCH", "/api/v1/rules/{rule_id}"): admin("viewer", "ops_boi", "cm_us", body=lambda c: {"name": "sweep"}),
    ("DELETE", "/api/v1/rules/{rule_id}"): admin("viewer", "ops_boi", "cm_us"),
    ("POST", "/api/v1/rules/{rule_id}/versions"): admin("viewer", "ops_boi", "cm_us", body=lambda c: {}),
    ("POST", "/api/v1/rules/{rule_id}/submit"): admin("viewer", "ops_boi", "cm_us"),
    ("POST", "/api/v1/rules/{rule_id}/approve"): admin("viewer", "ops_boi", "cm_us", body=lambda c: {}),
    ("POST", "/api/v1/rules/{rule_id}/reject"): admin("viewer", "ops_boi", "cm_us", body=lambda c: {"note": "sweep"}),
    ("POST", "/api/v1/rules/{rule_id}/rollback"): admin("viewer", "ops_boi", "cm_us"),
    # B4: pause/resume a kitchen's own offer (partners.edit or rules.approve in its city)
    ("POST", "/api/v1/rules/{rule_id}/pause"): admin("viewer", "ops_boi", "cm_us", "support_hyd", body=lambda c: {"reason": "Sweep"}),
    ("POST", "/api/v1/rules/{rule_id}/resume"): admin("viewer", "ops_boi", "cm_us", "support_hyd"),
    ("POST", "/api/v1/rules/{rule_id}/end"): admin("viewer", "ops_boi", "cm_us", body=lambda c: {}),
    ("GET", "/api/v1/markets"): admin(),
    ("POST", "/api/v1/markets/countries"): admin("cm_in", "viewer", body=lambda c: {
        "code": "GB", "name": "United Kingdom", "currency": "GBP", "locales": ["en-GB"], "timezone": "Europe/London",
        "phone_code": "+44", "payment_providers": ["stripe"], "tax_regime": "us_sales_tax"}),
    ("PATCH", "/api/v1/markets/countries/{country}"): admin("cm_us", "viewer", "ops_hyd", body=lambda c: {"name": "India"}),
    ("POST", "/api/v1/markets/countries/{country}/regions"): admin("cm_us", "viewer", "ops_hyd",
                                                                   body=lambda c: {"code": "IN-KA", "name": "Karnataka"}),
    ("PATCH", "/api/v1/markets/regions/{region}"): admin("cm_us", "viewer", "ops_boi", body=lambda c: {"name": "Telangana"}),
    ("POST", "/api/v1/markets/regions/{region}/cities"): admin("cm_us", "viewer", "ops_boi", body=lambda c: {
        "code": "IN-TG-WGL", "name": "Warangal", "center_lat": 17.97, "center_lng": 79.59}),
    ("GET", "/api/v1/markets/cities/{city}"): admin("ops_boi", "cm_us"),
    ("PATCH", "/api/v1/markets/cities/{city}"): admin("ops_boi", "cm_us", "viewer", body=lambda c: {"name": "Hyderabad"}),
    ("POST", "/api/v1/markets/cities/{city}/zones"): admin("ops_boi", "cm_us", "viewer",
                                                          body=lambda c: {"name": "Sweep", "polygon": POLYGON}),
    ("PATCH", "/api/v1/markets/zones/{zone_id}"): admin("ops_boi", "cm_us", "viewer", body=lambda c: {"name": "Sweep"}),
    ("POST", "/api/v1/markets/zones/{zone_id}/pause"): admin("ops_boi", "cm_us", "viewer", body=lambda c: {"reason": "sweep"}),
    ("POST", "/api/v1/markets/zones/{zone_id}/resume"): admin("ops_boi", "cm_us", "viewer"),
    ("GET", "/api/v1/audit"): admin(),
    # admin console (P21): cut to your scopes; another city's scope is refused
    ("GET", "/api/v1/ops/overview"): admin("ops_boi", params=lambda c: {"scope": "IN-TG-HYD"}),
    ("GET", "/api/v1/ops/orders"): admin("ops_boi", "finance_us", params=lambda c: {"scope": "IN-TG-HYD"}),
    ("GET", "/api/v1/riders/documents"): admin(),  # filtered to the countries you can see
    ("POST", "/api/v1/riders/documents/{document_id}/review"): admin("viewer", "ops_boi", "finance_in", "support_hyd",
                                                                    body=lambda c: {"decision": "approve"}),
    ("GET", "/api/v1/uploads/view"): admin("ops_boi", "finance_us", params=lambda c: {"key": c.rider_doc_key}),
    ("GET", "/api/v1/admin/me"): admin(),
    ("GET", "/api/v1/admin/role-assignments"): admin(),
    ("POST", "/api/v1/admin/role-assignments"): admin("viewer", "ops_hyd", "cm_us", body=lambda c: {
        "user_id": c.customer_id, "role": "country_manager", "scope": "IN"}),
    ("DELETE", "/api/v1/admin/role-assignments/{assignment_id}"): admin("viewer", "ops_boi", "cm_us"),
    ("GET", "/api/v1/users/{user_id}"): admin("other_customer", "ops_boi"),
    ("DELETE", "/api/v1/users/{user_id}/anonymize"): admin("other_customer", "viewer", "ops_boi"),
    # ── finance ──────────────────────────────────────────────────────────────
    ("GET", "/api/v1/finance/payout-runs"): admin(params=lambda c: {"country": "IN"}),
    ("POST", "/api/v1/finance/payout-runs"): admin("ops_hyd", "viewer", "finance_us", body=lambda c: {
        "country": "IN", "period_start": "2001-01-01", "period_end": "2001-01-08"}),
    ("GET", "/api/v1/finance/payout-runs/{run_id}"): admin("finance_us", "ops_boi"),
    ("POST", "/api/v1/finance/payout-runs/{run_id}/approve"): admin("finance_us", "ops_hyd", "viewer"),
    ("POST", "/api/v1/finance/payout-runs/{run_id}/retry"): admin("finance_us", "ops_hyd", "viewer"),
    ("GET", "/api/v1/finance/reconciliation"): admin("finance_us", "ops_boi", params=lambda c: {
        "country": "IN", "start": "2001-01-01", "end": "2001-01-08"}),
    ("GET", "/api/v1/finance/statements/{statement_id}"): user("other_partner", "other_rider", "customer", "finance_us"),
}


# ── resources owned by the "own" actors ─────────────────────────────────────

@dataclass
class Ctx:
    tokens: dict[str, dict]
    order: str = ""
    spice: str = ""
    item: str = ""
    group: str = ""
    address: str = ""
    quote: str = ""
    intent: str = ""
    intent_provider_id: str = ""
    rule: str = ""
    zone: str = ""
    run: str = ""
    statement: str = ""
    assignment: str = ""
    rider_doc: str = ""
    rider_doc_key: str = ""
    customer_id: str = ""
    rider_id: str = ""
    ticket: str = ""

    def path(self, template: str) -> str:
        values = {"order_id": self.order, "restaurant_id": self.spice, "item_id": self.item, "group_id": self.group,
                  "address_id": self.address, "quote_id": self.quote, "payment_intent_id": self.intent,
                  "rule_id": self.rule, "zone_id": self.zone, "run_id": self.run, "statement_id": self.statement,
                  "assignment_id": self.assignment, "user_id": self.customer_id, "rider_id": self.rider_id,
                  "offer_id": str(uuid.UUID(int=7)), "slug": "spice-route-kitchen-madhapur",
                  "document_id": self.rider_doc, "ticket_id": self.ticket,
                  "day": (date.today() + timedelta(days=30)).isoformat(),
                  "country": "IN", "region": "IN-TG", "city": "IN-TG-HYD", "code": "IN-TG-HYD"}
        return template.format(**values)


def _routes() -> list[tuple[str, str]]:
    from fastapi.routing import APIRoute

    from core_api.main import app

    out = set()
    for r in app.routes:
        if isinstance(r, APIRoute):
            out |= {(m, r.path) for m in r.methods}
        elif type(r).__name__ == "_IncludedRouter":
            out |= {(m, c.path) for c in r.effective_route_contexts() for m in (c.methods or ())}
    return sorted((m, p) for m, p in out if m != "HEAD")


# The markets paths name their code differently per level; POLICY uses readable placeholders.
_ALIASES = {"/api/v1/markets/countries/{code}": "/api/v1/markets/countries/{country}",
            "/api/v1/markets/countries/{code}/regions": "/api/v1/markets/countries/{country}/regions",
            "/api/v1/markets/regions/{code}": "/api/v1/markets/regions/{region}",
            "/api/v1/markets/regions/{code}/cities": "/api/v1/markets/regions/{region}/cities",
            "/api/v1/markets/cities/{code}": "/api/v1/markets/cities/{city}",
            "/api/v1/markets/cities/{code}/zones": "/api/v1/markets/cities/{city}/zones"}


def routes() -> list[tuple[str, str]]:
    return [(m, _ALIASES.get(p, p)) for m, p in _routes()]


@pytest.fixture(scope="module")
def ctx() -> Ctx:  # type: ignore[misc]
    """Built once in its own event loop; every test then runs in a fresh one."""
    import asyncio

    c = asyncio.run(_build())
    yield c
    asyncio.run(_teardown(c))


async def _teardown(c: Ctx) -> None:
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/v1/rules/{c.rule}/end", headers=_h(c, "cm_in"), json={})
    await close_redis()
    await engine.dispose()


def _h(c: Ctx, actor: str) -> dict:
    return {k: v for k, v in c.tokens[actor].items() if k != "_id"}


async def _build() -> Ctx:
    from sqlalchemy import text

    from core_api.integration.test_orders_flow import assign, move, new_order, pay
    from core_api.main import app
    from shared.db import AsyncSessionLocal, engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        from core_api.modules.identity.api.v1.auth import limiter

        tokens = {}
        for name, (email, pw) in ACTORS.items():
            limiter.reset()
            r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
            assert r.status_code == 200, (email, r.text)
            tokens[name] = {"Authorization": f"Bearer {r.json()['access_token']}", "_id": r.json()["user"]["id"]}
        c = Ctx(tokens)
        h = {k: v for k, v in tokens["customer"].items() if k != "_id"}
        order = await new_order(client, h)
        intent = await pay(client, h, order)
        partner = {k: v for k, v in tokens["partner"].items() if k != "_id"}
        rider = {k: v for k, v in tokens["rider"].items() if k != "_id"}
        for s in ("accepted", "preparing", "ready"):
            await move(client, partner, order["id"], s)
        await assign(client, order["id"], rider)
        for s in ("picked_up", "delivered"):
            await move(client, rider, order["id"], s)
        c.order, c.intent = order["id"], intent["payment_intent_id"]
        c.intent_provider_id = intent.get("provider_payment_id") or intent.get("razorpay_order_id") or "order_x"
        c.spice = order["restaurant_id"]
        c.item = order["items"][0]["menu_item_id"]
        c.customer_id, c.rider_id = tokens["customer"]["_id"], tokens["rider"]["_id"]
        r = await client.post("/api/v1/me/addresses", headers=h, json={"street": "Sweep", "city": "Hyderabad"})
        c.address = r.json()["id"]
        r = await client.post("/api/v1/pricing/quote", headers=h, json={
            "restaurant_id": c.spice, "items": _items(c), "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
        c.quote = r.json()["quote_id"]
        r = await client.post(f"{R.format(restaurant_id=c.spice)}/option-groups", headers=partner, json=OPTION_GROUP)
        c.group = r.json()["id"]
        r = await client.post(f"{R.format(restaurant_id=c.spice)}/callback", headers=partner, json={"topic": "other", "note": "Access sweep"})
        c.ticket = r.json()["id"]
        cm = {k: v for k, v in tokens["cm_in"].items() if k != "_id"}
        r = await client.post("/api/v1/rules", headers=cm, json={
            "family": "business", "template": "cancel_window", "params": {"minutes": 2}, "name": "Access sweep",
            "scope_level": "city", "scope_id": "IN-TG-HYD"})
        c.rule = r.json()["id"]
        async with AsyncSessionLocal() as db:
            c.zone = str((await db.execute(text(
                "SELECT z.id FROM zones z JOIN cities ci ON ci.id = z.city_id WHERE ci.code = 'IN-TG-HYD' LIMIT 1"))).scalar())
            row = (await db.execute(text(
                "SELECT d.id, d.file_key FROM rider_documents d JOIN users u ON u.id = d.rider_id "
                "WHERE u.email = 'rider1.hyd@example.com' AND d.kind = 'licence'"))).one()
            c.rider_doc, c.rider_doc_key = str(row[0]), row[1]
            c.assignment = str((await db.execute(text(
                "SELECT a.id FROM admin_role_assignments a JOIN users u ON u.id = a.user_id "
                "WHERE u.email = 'ops.hyd@example.com' LIMIT 1"))).scalar())
            # A payout run in the distant past with statements for Spice Route and the rider.
            from core_api.modules.finance.models import PayoutRun, PayoutStatement

            start = date(2001, 1, 1) + timedelta(weeks=uuid.uuid4().int % 500)
            run = PayoutRun(country="IN", currency="INR", period_start=start, period_end=start + timedelta(days=7),
                            status="draft", totals={}, created_by=uuid.UUID(c.customer_id))
            db.add(run)
            await db.flush()
            st = PayoutStatement(run_id=run.id, payee_type="restaurant", payee_id=uuid.UUID(c.spice),
                                 payee_name="Spice Route Kitchen", currency="INR", amount=0, summary={}, lines=[])
            db.add(st)
            await db.flush()
            run_id, st_id = run.id, st.id
            await db.commit()
            c.run, c.statement = str(run_id), str(st_id)
    await close_redis()
    await engine.dispose()
    return c


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def call(client: AsyncClient, c: Ctx, method: str, template: str, actor: str | None, headers: dict | None = None):  # type: ignore[no-untyped-def]
    p = POLICY[(method, template)]
    h = {k: v for k, v in (c.tokens[actor] if actor else {}).items() if k != "_id"}
    kw: dict[str, Any] = {"headers": {**h, **(headers or {})}}
    if p.body:
        kw["json"] = p.body(c)
    if p.params:
        kw["params"] = p.params(c)
    return await client.request(method, c.path(template), **kw)


# ── the tests ────────────────────────────────────────────────────────────────

def test_every_route_has_a_policy() -> None:
    have = set(routes())
    missing = sorted(have - set(POLICY))
    stale = sorted(set(POLICY) - have)
    assert not missing, f"routes with no access policy (add them to POLICY): {missing}"
    assert not stale, f"POLICY entries for routes that no longer exist: {stale}"


PROTECTED = [k for k, p in POLICY.items() if p.kind != "public"]


@pytest.mark.parametrize(("method", "path"), PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
async def test_no_token_is_refused(client: AsyncClient, ctx: Ctx, method: str, path: str) -> None:
    r = await call(client, ctx, method, path, None)
    want = {401} if POLICY[(method, path)].kind == "signed" else NO_TOKEN
    assert r.status_code in want, f"{method} {path} without a token → {r.status_code} {r.text[:200]}"


SIGNED = [k for k, p in POLICY.items() if p.kind == "signed"]


@pytest.mark.parametrize(("method", "path"), SIGNED, ids=[f"{m} {p}" for m, p in SIGNED])
async def test_internal_endpoints_refuse_user_tokens(client: AsyncClient, ctx: Ctx, method: str, path: str) -> None:
    for actor in ("customer", "rider", "ops_hyd"):
        r = await call(client, ctx, method, path, actor)
        assert r.status_code == 401, f"{method} {path} as {actor} → {r.status_code}"


CASES = [(m, p, a) for (m, p), pol in POLICY.items() for a in pol.refused]


@pytest.mark.parametrize(("method", "path", "actor"), CASES, ids=[f"{m} {p} as {a}" for m, p, a in CASES])
async def test_wrong_role_or_someone_elses_resource_is_refused(client: AsyncClient, ctx: Ctx, method: str, path: str,
                                                               actor: str) -> None:
    r = await call(client, ctx, method, path, actor)
    assert r.status_code in REFUSED, f"{method} {path} as {actor} → {r.status_code} {r.text[:300]}"


def test_public_routes_are_deliberate() -> None:
    assert all(p.why for p in POLICY.values() if p.kind == "public")
