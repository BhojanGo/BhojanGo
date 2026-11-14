"""Signed calls from realtime to core_api's internal order endpoints (P14)."""
import json

import httpx

from shared import internal_auth
from shared.config import get_settings


class CoreApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class CoreApi:
    async def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else b""
        headers = {"content-type": "application/json", **internal_auth.sign(method, path, data)}
        async with httpx.AsyncClient(base_url=get_settings().CORE_API_URL, timeout=10) as client:
            r = await client.request(method, path, content=data or None, headers=headers)
        if r.status_code >= 400:
            try:
                message = r.json().get("detail", {}).get("message") or r.text
            except Exception:  # noqa: BLE001
                message = r.text
            raise CoreApiError(r.status_code, str(message))
        return r.json()

    async def dispatch_info(self, order_id: str) -> dict:
        return await self._call("GET", f"/api/v1/internal/orders/{order_id}/dispatch")

    async def assign_rider(self, order_id: str, rider_id: str, batch_id: str | None = None, position: int | None = None) -> dict:
        body: dict = {"rider_id": rider_id}
        if batch_id:
            body |= {"batch_id": batch_id, "batch_position": position}
        return await self._call("POST", f"/api/v1/internal/orders/{order_id}/assign-rider", body)

    async def rider_ready(self, rider_id: str) -> dict:
        """Has the rider finished onboarding (documents approved, background check cleared)?"""
        return await self._call("GET", f"/api/v1/internal/riders/{rider_id}/ready")

    async def city_centre(self, code: str) -> tuple[float, float] | None:
        """Where a city is (public GET /markets/cities), for the dispatch map."""
        async with httpx.AsyncClient(base_url=get_settings().CORE_API_URL, timeout=10) as client:
            r = await client.get("/api/v1/markets/cities")
        if r.status_code != 200:
            raise CoreApiError(r.status_code, r.text)
        c = next((x for x in r.json() if x["code"] == code), None)
        return (c["lat"], c["lng"]) if c else None


core_api = CoreApi()
