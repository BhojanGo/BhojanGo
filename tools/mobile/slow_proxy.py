"""A pass-through HTTP proxy in front of the local core API that can hold chosen
requests, so a screenshot can catch a loading state (CustomerLoading.html).
Used only by .github/workflows/app-screens.yml on a throwaway stack.

    python tools/mobile/slow_proxy.py 8011 http://localhost:8001

The app talks to the proxy; everything goes straight through until a flow asks
for a hold (Maestro runScript, from the host):
    GET /__slow/on?path=/api/v1/discover   requests starting with that path wait
    GET /__slow/off                        they go through again (held ones too)
A held request waits at most 120 s.
"""
import http.client
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PORT = int(sys.argv[1])
UPSTREAM = urlsplit(sys.argv[2])
HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-connection", "host"}

state = {"prefix": None}
release = threading.Event()
release.set()


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: ANN001, ANN002
        sys.stderr.write("proxy: " + (fmt % args) + "\n")

    def _control(self) -> bool:
        url = urlsplit(self.path)
        if not url.path.startswith("/__slow/"):
            return False
        if url.path == "/__slow/on":
            state["prefix"] = (parse_qs(url.query).get("path") or ["/"])[0]
            release.clear()
        else:
            state["prefix"] = None
            release.set()
        body = f"hold: {state['prefix']}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def _forward(self) -> None:
        if self._control():
            return
        prefix = state["prefix"]
        if prefix and self.path.startswith(prefix):
            release.wait(120)
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
