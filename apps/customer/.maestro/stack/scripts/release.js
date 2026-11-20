// Let the held kitchens request through (tools/mobile/slow_proxy.py). R23: it must still be
// waiting at the proxy, so the loading state the flow just saw is the hold's, and the app
// hasn't given up on it (the content that follows comes from this very request).
var let_go = http.get("http://localhost:8011" + "/__slow/off");
var released = Number((/released: (\d+)/.exec(let_go.body) || [])[1] || 0);
if (released < 1) throw new Error("nothing was held when released: " + let_go.body);
output.released = released;
