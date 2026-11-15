// Let held requests through again (tools/mobile/slow_proxy.py).
http.get("http://localhost:8011" + "/__slow/off");
