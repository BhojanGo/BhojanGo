"""Repository-wide conventions that are easy to break by accident."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def test_db_sessions_commit_before_the_response() -> None:
    """Depends(get_db) without scope="function" commits after the response is
    sent, so a client can read a stale database right after a write."""
    offenders = [
        str(p.relative_to(BACKEND))
        for area in ("core_api", "realtime", "worker")
        for p in (BACKEND / area).rglob("*.py")
        if p.name != "test_conventions.py" and "Depends(get_db)" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
