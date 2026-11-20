"""A pass-through HTTP proxy in front of the local core API that can hold chosen
requests, so a screenshot can catch a loading state (CustomerLoading.html).
Used only by .github/workflows/app-screens.yml on a throwaway stack.

    python tools/mobile/slow_proxy.py 8011 http://localhost:8001

The app talks to the proxy; everything goes straight through until a flow asks
for a hold (Maestro runScript, from the host):
    GET /__slow/on?path=/api/v1/discover?lat=   requests starting with that path wait
    GET /__slow/status                          the hold and how many requests wait in it
    GET /__slow/off                             they go through again (held ones too);
                                                answers "released: <n>", the requests
                                                that were still waiting

R23: no timer decides what the app sees. A held request waits until the flow lets it
go, and the app's own GET timeout is lifted on this stack (EXPO_PUBLIC_TEST_GET_TIMEOUT_MS,
tools/mobile/stack-screens.sh), so the app can't give up first. If no release ever comes,
the request fails with 504 after HOLD_CAP_S (it never goes through on its own), so a
missing release fails the flow instead of quietly passing it.
"""
import http.client
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PORT = int(sys.argv[1])
UPSTREAM = urlsplit(sys.argv[2])
HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-connection", "host"}
HOLD_CAP_S = 120  # a safety net only; the app's test timeout (150 s) is longer

lock = threading.Lock()
# The current hold: its path prefix, its gate (a new Event per hold) and who waits at it.
state = {"prefix": None, "gate": threading.Event(), "waiting": 0}
state["gate"].set()


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("proxy: " + (fmt % args) + "\n")

    def _control(self) -> bool:
        url = urlsplit(self.path)
        if not url.path.startswith("/__slow/"):
            return False
        with lock:
            if url.path == "/__slow/on":
                state["gate"].set()  # an earlier hold never left anything waiting
                state["gate"] = threading.Event()
                state["prefix"] = (parse_qs(url.query).get("path") or ["/"])[0]
                text = f"hold: {state['prefix']}\n"
            elif url.path == "/__slow/status":
                text = f"hold: {state['prefix']}\nwaiting: {state['waiting']}\n"
            else:
                text = f"released: {state['waiting']}\n"
                state["prefix"] = None
                state["gate"].set()
        self.log_message("%s", text.strip().replace("\n", ", "))
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def _hold(self) -> bool:
        """Wait while this request is held; False if the hold was never released."""
        with lock:
            prefix, gate = state["prefix"], state["gate"]
            if not (prefix and self.path.startswith(prefix)):
                return True
            state["waiting"] += 1
        self.log_message("held %s", self.path)
        try:
            return gate.wait(HOLD_CAP_S)
        finally:
            with lock:
                state["waiting"] -= 1

    def _forward(self) -> None:
        if self._control():
            return
        if not self._hold():
            self.send_error(504, "held, never released")
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        conn = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port or 80, timeout=60)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            r = conn.getresponse()
            data = r.read()
        except OSError as e:
            self.send_error(502, str(e))
            return
        finally:
            conn.close()
        self.send_response(r.status, r.reason)
        for k, v in r.getheaders():
            if k.lower() not in HOP and k.lower() != "content-length":
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = _forward


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Proxy).serve_forever()
