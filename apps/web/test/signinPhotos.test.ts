// node --test: R23. The sign-in pages' photo grid (signin/Shell.tsx) has four tiles on a
// desktop and two on a phone; kitchens' covers come from discover and may be fewer than
// that (or none). The country's hero dish and other library dishes fill the rest, so no
// tile is ever empty, no photo shows twice, and every filler photo is on the website.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import { signInPhotos } from "../src/lib/format.ts";

const here = new URL(".", import.meta.url);
const library = JSON.parse(readFileSync(new URL("../src/content/photo-library.json", here), "utf-8")) as string[];
const cover = (i: number) => `https://cdn.example.test/kitchens/k${i}/cover-800.webp`;
const DESKTOP = 4;
const PHONE = 2;

for (const count of [0, 1, 2, 3]) {
  test(`discover returns ${count} cover(s): every desktop and phone tile still has a photo`, () => {
    const covers = Array.from({ length: count }, (_, i) => cover(i));
    const tiles = signInPhotos(covers, "masala-dosa", library);
    assert.equal(tiles.length, DESKTOP);
    for (let i = 0; i < DESKTOP; i++) assert.ok(tiles[i], `desktop tile ${i + 1} is empty`);
    for (let i = 0; i < PHONE; i++) assert.ok(tiles[i], `phone tile ${i + 1} is empty`);
    assert.equal(new Set(tiles).size, DESKTOP, "a photo shows twice");
    assert.deepEqual(tiles.slice(0, count), covers, "kitchens' covers come first");
    if (count < DESKTOP) assert.equal(tiles[count], "/food/masala-dosa-800.webp", "then the country's hero dish");
  });
}

test("fillers are library food photos the website has (never a scooter or a cook)", () => {
  for (const hero of [null, "poke-bowl", "north-indian-thali", "not a slug!"]) {
    const tiles = signInPhotos([], hero, library);
    assert.equal(tiles.length, DESKTOP);
    assert.equal(new Set(tiles).size, DESKTOP);
    for (const t of tiles) {
      const m = /^\/food\/([a-z0-9-]+)-800\.webp$/.exec(t);
      assert.ok(m, `${t} isn't a library photo`);
      assert.ok(library.includes(m[1]!), `${m[1]} isn't in the library`);
      assert.ok(!["delivery-partner-scooter", "kitchen-cook"].includes(m[1]!));
      assert.ok(existsSync(new URL(`../public/food/${m[1]}-800.webp`, here)), `${t} is missing from public/food`);
    }
  }
});

test("duplicate and missing covers are skipped; four or more covers need no filler", () => {
  assert.deepEqual(signInPhotos([cover(1), null, cover(1), "", undefined], null, library).slice(0, 1), [cover(1)]);
  assert.equal(signInPhotos([cover(1), null, cover(1)], null, library).length, DESKTOP);
  const many = [1, 2, 3, 4, 5].map(cover);
  assert.deepEqual(signInPhotos(many, "masala-dosa", library), many.slice(0, 4));
});

test("the sign-in frame draws its tiles from signInPhotos and the library list", () => {
  const shell = readFileSync(new URL("../src/app/signin/Shell.tsx", here), "utf-8");
  assert.match(shell, /signInPhotos\(covers, [^)]*library\)/);
  assert.match(shell, /\[0, 1, 2, 3\]\.map/);
});
