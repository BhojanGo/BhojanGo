// Hold the kitchens request at tools/mobile/slow_proxy.py (runs on the host, not the phone).
http.get("http://localhost:8011" + "/__slow/on?path=/api/v1/discover");
