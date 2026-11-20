// Hold the home's kitchens request (GET /discover?lat=..&lng=..) at tools/mobile/slow_proxy.py
// (runs on the host, not the phone) until release.js lets it go. Only the home's request:
// the sign-in collage's GET /discover?city= goes through. No timer: the app's own GET
// timeout is lifted on this stack (EXPO_PUBLIC_TEST_GET_TIMEOUT_MS, stack-screens.sh).
var held = http.get("http://localhost:8011" + "/__slow/on?path=/api/v1/discover?lat=");
if (held.status !== 200) throw new Error("hold not set: " + held.status + " " + held.body);
