// Generates the background of the macOS .dmg (assets/dmg/): 660 x 400 points, as a PNG at 1x and 2x and a
// two-resolution TIFF that the bundler takes (bundle.macOS.dmg in src-tauri/tauri.conf.json). Pixel art in the look of
// the page background and the README banner (own artwork, own colours from DESIGN.md, no Korg assets), text in Sora.
// The icons of the app and of the Applications folder sit where tauri.conf.json puts them: x 180 and 480, y 215.
//
//   node tools/dmg-background.mjs      needs playwright with Chrome and, for the TIFF, macOS (tiffutil)

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { resizedHead } from "./blechy-head.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "assets", "dmg");
const WIDTH = 660;
const HEIGHT = 400;
const CELL = 4;
const W = WIDTH / CELL;
const H = HEIGHT / CELL;
const BG = "#0a0a0b";
const ACCENT = "#9ec3d1";
const FG = "#fafafa";

const grid = Array.from({ length: H }, () => new Array(W).fill(" "));
const put = (x, y, c) => {
  if (x >= 0 && y >= 0 && x < W && y < H) grid[y][x] = c;
};

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// Dither bands at both sides, thinning out towards the middle, like bg.js and the banner.
for (let j = 0; j < H; j += 2) {
  for (let i = 0; i < W; i += 2) {
    const edge = Math.min(i, W - 1 - i);
    if (edge < 20 && ((i / 2 + j / 2) % 2 === 0 || (i * 7 + j * 3) % 5 === 0) && edge * 2 < 40 - ((i * 13 + j * 7) % 17)) put(i, j, "F");
  }
}
// Stars between the bands, kept off the icon row and the text.
const random = rng(11);
for (let n = 0; n < 40; n++) {
  const x = 24 + Math.floor(random() * (W - 48));
  const y = Math.floor(random() * H);
  const onIcons = y > 34 && y < 78;
  const onText = (y > 14 && y < 34) || y > 84;
  if (!onIcons && !onText) put(x, y, random() < 0.3 ? "S" : "F");
}

// Blechy above the title.
const head = resizedHead(22, 14);
const headX = Math.floor((W - head[0].length) / 2);
head.forEach((row, y) => [...row].forEach((pixel, x) => { if (pixel === "#") put(headX + x, 3 + y, "W"); }));

// The arrow from the app to the folder: a shaft and a head, 8 points thick.
const rowMid = Math.round(215 / CELL);
for (let i = 69; i < 91; i++) for (const j of [rowMid - 1, rowMid]) put(i, j, "A");
for (let d = 0; d < 6; d++) for (let j = rowMid - 6 + d; j <= rowMid + 5 - d; j++) put(91 + d, j, "A");

const runs = (chars) => {
  let d = "";
  for (let j = 0; j < H; j++) {
    for (let i = 0; i < W;) {
      if (!chars.includes(grid[j][i])) { i++; continue; }
      let k = i;
      while (k < W && chars.includes(grid[j][k])) k++;
      d += `M${i} ${j}h${k - i}v1h-${k - i}z`;
      i = k;
    }
  }
  return d;
};
const layer = (chars, fill, opacity) => `<path fill="${fill}" fill-opacity="${opacity}" d="${runs(chars)}"/>`;
const art = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${WIDTH}" height="${HEIGHT}" shape-rendering="crispEdges">
<rect width="${W}" height="${H}" fill="${BG}"/>${layer("F", ACCENT, 0.3)}${layer("S", ACCENT, 0.6)}${layer("A", ACCENT, 1)}${layer("W", FG, 1)}</svg>`;

const font = `data:font/woff2;base64,${readFileSync(join(root, "site/design/fonts/sora-latin.woff2")).toString("base64")}`;
const page = `<!doctype html><meta charset="utf-8"><style>
@font-face { font-family: Sora; src: url("${font}"); font-weight: 100 800; }
html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; background: ${BG}; overflow: hidden; font-family: Sora, sans-serif; text-align: center; }
svg { position: absolute; inset: 0; }
h1 { position: absolute; top: 80px; left: 0; right: 0; margin: 0; font-size: 26px; font-weight: 700; line-height: 1.1; color: ${FG}; letter-spacing: -0.5px; }
p { position: absolute; left: 0; right: 0; margin: 0; }
.lead { top: 117px; font-size: 14px; color: rgba(255, 255, 255, 0.72); }
.hint { top: 352px; font-size: 12px; color: rgba(255, 255, 255, 0.55); }
</style>${art}
<h1>Kuhlers GELUMPE</h1>
<p class="lead">Zieh die App auf den Ordner Programme.</p>
<p class="hint">Wird der Start blockiert? Die README hilft unter „Die App laden“.</p>`;

mkdirSync(out, { recursive: true });
const { chromium } = await import("playwright");
const browser = await chromium.launch({ channel: "chrome" });
try {
  for (const [scale, name] of [[1, "background.png"], [2, "background@2x.png"]]) {
    const tab = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: scale });
    await tab.setContent(page);
    await tab.evaluate(() => document.fonts.ready);
    writeFileSync(join(out, name), await tab.screenshot());
    await tab.close();
  }
} finally {
  await browser.close();
}
const tiff = join(out, "background.tiff");
execFileSync("tiffutil", ["-cathidpicheck", join(out, "background.png"), join(out, "background@2x.png"), "-out", tiff]);
execFileSync("tiffutil", ["-lzw", tiff, "-out", tiff]);
console.log(`wrote ${out} (${readFileSync(tiff).length} bytes TIFF)`);
