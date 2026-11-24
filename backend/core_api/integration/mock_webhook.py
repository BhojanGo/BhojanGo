"""A local HTTP endpoint that records JSON POSTs: the paging webhook in tests (R39)."""
from __future__ import annotations

import http.server
import json
import threading
from typing import Any


class MockWebhook:
    def __init__(self, status: int = 200) -> None:
        self.received: list[dict[str, Any]] = []
        self.status = status
        hook = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                n = int(self.headers.get("Content-Length") or 0)
                hook.received.append(json.loads(self.rfile.read(n) or b"{}"))
                self.send_response(hook.status)
                self.end_headers()

            def log_message(self, *args: Any) -> None:
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/hook"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> MockWebhook:
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()
