"""R8 F10: the retention job's pieces without a database: batching until nothing is
left, the cut-off dates it asks for, and delivery routes always expiring within a day."""
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from app.services import retention


class FakeDb:
    """Answers DELETEs with the row counts given, recording the cut-offs asked for."""

    def __init__(self, counts: list[int]) -> None:
        self.counts, self.params = list(counts), []

    async def execute(self, _sql, params):  # type: ignore[no-untyped-def]
        self.params.append(params)
        n = self.counts.pop(0) if self.counts else 0

        class R:
            rowcount = n
        return R()


NOW = datetime(2027, 3, 1, 12, tzinfo=UTC)


async def test_messages_go_after_90_days_in_batches() -> None:
    db = FakeDb([retention.BATCH, retention.BATCH, 7])
    assert await retention.purge_order_messages(db, NOW) == 2 * retention.BATCH + 7
    assert len(db.params) == 3  # stops once a batch comes back short
    assert db.params[0]["cutoff"] == NOW - timedelta(days=90) and db.params[0]["batch"] == retention.BATCH


async def test_resolved_tickets_go_after_three_years() -> None:
    db = FakeDb([0])
    assert await retention.purge_resolved_tickets(db, NOW) == 0
    assert db.params[0]["cutoff"] == NOW - timedelta(days=3 * 365)


async def test_every_route_expires_within_a_day() -> None:
    r = fakeredis.FakeAsyncRedis(decode_responses=True)
    await r.rpush("trail:no-expiry", "x")
    await r.rpush("trail:too-long", "x")
    await r.expire("trail:too-long", 7 * 24 * 3600)
    await r.rpush("trail:fine", "x")
    await r.expire("trail:fine", 3600)
    await r.set("rider:1:state", "x")  # not a route: left alone
    assert await retention.cap_route_trails(r) == 2
    assert 0 < await r.ttl("trail:no-expiry") <= retention.ROUTE_KEEP_SECONDS
    assert 0 < await r.ttl("trail:too-long") <= retention.ROUTE_KEEP_SECONDS
    assert await r.ttl("trail:fine") <= 3600
    assert await r.ttl("rider:1:state") == -1
    assert await retention.cap_route_trails(r) == 0  # idempotent


def test_the_periods_match_the_privacy_notices() -> None:
    from pathlib import Path

    notices = Path(__file__).resolve().parents[3] / "tools" / "seed" / "legal"
    if not notices.is_dir():
        pytest.skip("the seed's documents aren't in this image")
    for country in ("IN", "US"):
        text = (notices / f"{country}-privacy.md").read_text(encoding="utf-8")
        assert "deleted 90 days after they were sent" in text
        assert "3 years after they were resolved" in text
        assert "one day" in text
    assert retention.MESSAGES_KEEP.days == 90 and retention.TICKETS_KEEP.days == 3 * 365
    assert retention.ROUTE_KEEP_SECONDS == 24 * 3600
