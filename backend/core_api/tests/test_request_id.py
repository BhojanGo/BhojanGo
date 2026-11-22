"""R28: an app's X-Request-ID is the id on the API's request log lines and on the response,
so a request that failed in the app can be found in the API's logs (or shown never to have arrived)."""
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from structlog.testing import capture_logs

from shared.middleware.correlation import CorrelationMiddleware
from shared.middleware.logging import RequestLoggingMiddleware


def _app() -> Starlette:
    app = Starlette(routes=[Route("/q", lambda r: PlainTextResponse("ok"), methods=["POST"])])
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationMiddleware)  # outermost, as in core_api/main.py
    return app


def test_the_callers_request_id_is_logged_and_returned():
    with capture_logs() as logs, TestClient(_app()) as c:
        r = c.post("/q", headers={"X-Request-ID": "app-7f3a"})
    assert r.headers["X-Request-ID"] == "app-7f3a"
    done = [e for e in logs if e["event"] == "request_completed"]
    assert done and done[0]["request_id"] == "app-7f3a" and done[0]["status_code"] == 200


def test_without_one_the_log_and_the_response_share_a_new_id():
    with capture_logs() as logs, TestClient(_app()) as c:
        r = c.post("/q")
    rid = r.headers["X-Request-ID"]
    assert rid and [e["request_id"] for e in logs if e["event"] == "request_completed"] == [rid]
