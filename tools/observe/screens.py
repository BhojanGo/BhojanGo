"""Screenshot for P23 (Playwright image on the compose network, see
docs/runbooks/observe.md): a firing alert in the admin console's Operations
page. Grafana's dashboards are seen in a browser at http://localhost:3300."""
import os
import re
import socket
import threading

from playwright.sync_api import sync_playwright

OUT = os.environ.get("OUT", "/out")
FORWARD = {3001: ("admin", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}


def forward(port: int, target: tuple[str, int]) -> None:
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(64)

    def pipe(a: socket.socket, b: socket.socket) -> None:
        try:
            while data := a.recv(65536):
                b.sendall(data)
        except OSError:
            pass
        finally:
            a.close()
            b.close()

    def serve() -> None:
        while True:
            c, _ = srv.accept()
            u = socket.create_connection(target)
            threading.Thread(target=pipe, args=(c, u), daemon=True).start()
            threading.Thread(target=pipe, args=(u, c), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()


for port, target in FORWARD.items():
    forward(port, target)

with sync_playwright() as p:
    b = p.chromium.launch()
    a = b.new_page(viewport={"width": 1440, "height": 900})
    a.goto("http://localhost:3001/login", wait_until="networkidle")
    a.locator("input[type=email]").fill("ops.hyd@example.com")
    a.locator("input[type=password]").fill("BhojanGoAdmin1")
    a.get_by_role("button", name=re.compile("sign in", re.I)).click()
    a.wait_for_url("**/overview**", timeout=20000)
    a.goto("http://localhost:3001/operations?scope=IN-TG-HYD&tab=live", wait_until="networkidle")
    a.get_by_role("region", name="Alerts").wait_for(timeout=20000)
    a.screenshot(path=f"{OUT}/01-admin-alert.png")
    print("ok")
