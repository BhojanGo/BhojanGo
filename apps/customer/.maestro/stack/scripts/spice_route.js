// Spice Route Kitchen's id from the local core API (public list), for bhojango://restaurant/<id>.
// Runs on the host; throwaway stack only.
var list = json(http.get("http://localhost:8001/api/v1/restaurants?limit=50").body).items;
for (var i = 0; i < list.length; i++) {
  if (list[i].name === "Spice Route Kitchen") output.kitchen = list[i].id;
}
if (!output.kitchen) throw new Error("Spice Route Kitchen not found");
