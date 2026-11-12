// Every app icon, adaptive icon, splash image, notification icon and favicon,
// generated from the logo SVGs in docs/design/logo (P16).
//   pnpm brand:assets
// Re-run after changing a logo; commit the PNGs it writes.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const logo = (name) => readFileSync(join(root, "docs/design/logo", name), "utf8");
const MARK = { teal: logo("mark-teal.svg"), white: logo("mark-white.svg") };

/** The mark drawn in one colour (Android notification icons must be white on transparent). */
const silhouette = MARK.white.replace(/#E8A93C/g, "#FFFFFF");

async function png(svg, size, out, { scale = 1, background = { r: 0, g: 0, b: 0, alpha: 0 } } = {}) {
  mkdirSync(dirname(out), { recursive: true });
  const inner = Math.round(size * scale);
  const art = await sharp(Buffer.from(svg), { density: 600 }).resize(inner, inner).png().toBuffer();
  await sharp({ create: { width: size, height: size, channels: 4, background } })
    .composite([{ input: art, gravity: "center" }])
    .png()
    .toFile(out);
  return out;
}

/** A .ico holding PNG images (16, 32, 48): browsers and Windows read PNG-in-ICO. */
async function ico(svg, out) {
  const sizes = [16, 32, 48];
  const images = await Promise.all(sizes.map((s) => sharp(Buffer.from(svg), { density: 600 }).resize(s, s).png().toBuffer()));
  const header = Buffer.alloc(6 + 16 * sizes.length);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(sizes.length, 4);
  let offset = header.length;
  sizes.forEach((s, i) => {
    const e = 6 + 16 * i;
    header.writeUInt8(s, e);
    header.writeUInt8(s, e + 1);
    header.writeUInt16LE(1, e + 4);
    header.writeUInt16LE(32, e + 6);
    header.writeUInt32LE(images[i].length, e + 8);
    header.writeUInt32LE(offset, e + 12);
    offset += images[i].length;
  });
  writeFileSync(out, Buffer.concat([header, ...images]));
  return out;
}

const hex = (h) => ({ r: parseInt(h.slice(1, 3), 16), g: parseInt(h.slice(3, 5), 16), b: parseInt(h.slice(5, 7), 16), alpha: 1 });

// The three apps: icon from the pack, adaptive-icon foreground (the mark inside
// Android's safe zone, ~60%) over the icon's ground, splash mark.
const APPS = {
  customer: { icon: "icon-customer.svg", ground: "#0B5D66", foreground: MARK.white, splash: MARK.teal },
  rider: { icon: "icon-rider.svg", ground: "#E8A93C", foreground: logo("icon-rider.svg").replace(/<rect[^>]*\/>/, ""), splash: MARK.white },
  partner: { icon: "icon-partner.svg", ground: "#FFFFFF", foreground: MARK.teal, splash: MARK.teal },
};

const written = [];
for (const [app, a] of Object.entries(APPS)) {
  const dir = join(root, "apps", app, "assets");
  written.push(await png(logo(a.icon), 1024, join(dir, "icon.png")));
  written.push(await png(a.foreground, 1024, join(dir, "adaptive-icon.png"), { scale: 0.6 }));
  written.push(await png(a.splash, 512, join(dir, "splash-icon.png")));
  written.push(await png(silhouette, 96, join(dir, "notification-icon.png"), { scale: 0.9 }));
  written.push(await png(logo(a.icon), 48, join(dir, "favicon.png")));
}

// Web and admin (Next.js app-directory icon files).
for (const [app, svg, bg] of [["web", logo("icon-customer.svg"), null], ["admin", MARK.teal, "#F4F6F6"]]) {
  const dir = join(root, "apps", app, "src", "app");
  const opts = bg ? { background: hex(bg), scale: 0.78 } : {};
  written.push(await png(svg, 512, join(dir, "icon.png"), opts));
  written.push(await png(svg, 180, join(dir, "apple-icon.png"), opts));
  written.push(await ico(svg, join(dir, "favicon.ico")));
}

console.log(written.map((p) => p.slice(root.length + 1)).join("\n"));
