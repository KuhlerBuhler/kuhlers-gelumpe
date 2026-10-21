// Generates the README banner in assets/readme/ (dark and light SVG, optional PNG).
// Everything sits on a 320 x 80 cell grid (1 cell = 4 px of the 1280 x 320
// image), in the 1-bit look of the BLECH splash and the app icon. Own artwork,
// own pixel font, no Korg assets and no device photos.
//
//   node tools/readme-banner.mjs            write the SVGs
//   node tools/readme-banner.mjs --png      also render PNGs and preview.png (needs playwright)
//   node tools/readme-banner.mjs --ascii    print the grid

import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { tmpdir } from "node:os";
import { resizedHead } from "./blechy-head.mjs";

const W = 320;
const H = 80;
const CELL = 4;

// Theme colours. dark: the design system page + accent; light: paper and a darker accent.
const THEMES = {
  dark: { bg: "#0a0a0b", accent: "#9ec3d1", fg: "#fafafa", faint: 0.3, muted: 0.78, pad: 0.14 },
  light: { bg: "#eef3f5", accent: "#2d6579", fg: "#0a0a0b", faint: 0.26, muted: 0.85, pad: 0.12 },
};

// ---------- 5x7 pixel font (own drawing) ----------
const FONT = {
  A: [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
  B: ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
  C: [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
  D: ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
  E: ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
  F: ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
  G: [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
  H: ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
  I: [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
  J: ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
  K: ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
  L: ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
  M: ["#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"],
  N: ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
  O: [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  P: ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
  Q: [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
  R: ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
  S: [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
  T: ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
  U: ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  V: ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
  W: ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
  X: ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
  Y: ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
  Z: ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
  u: [".....", ".....", "#...#", "#...#", "#...#", "#..##", ".##.#"],
  h: ["#....", "#....", "#.##.", "##..#", "#...#", "#...#", "#...#"],
  l: [".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
  e: [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
  r: [".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."],
  s: [".....", ".....", ".####", "#....", ".###.", "....#", "####."],
  "'": ["#", "#", ".", ".", ".", ".", "."],
  ".": [".", ".", ".", ".", ".", ".", "#"],
  ",": [".", ".", ".", ".", ".", "#", "#"],
  a: [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
  b: ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
  c: [".....", ".....", ".###.", "#....", "#....", "#...#", ".###."],
  d: ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
  f: ["..##.", ".#...", "####.", ".#...", ".#...", ".#...", ".#..."],
  i: ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
  m: [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#...#", "#...#"],
  n: [".....", ".....", "#.##.", "##..#", "#...#", "#...#", "#...#"],
  o: [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
  p: [".....", ".....", "####.", "#...#", "#...#", "####.", "#...."],
  t: [".#...", ".#...", "###..", ".#...", ".#...", ".#..#", "..##."],
  z: [".....", ".....", "#####", "...#.", "..#..", ".#...", "#####"],
  "-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
  " ": ["...", "...", "...", "...", "...", "...", "..."],
};

const glyphW = (ch) => (FONT[ch] || FONT[" "])[0].length;
const textWidth = (s, scale, gap = 1) =>
  [...s].reduce((w, ch, i) => w + glyphW(ch) * scale + (i ? gap * scale : 0), 0);

// ---------- grid ----------
const grid = () => Array.from({ length: H }, () => new Array(W).fill(" "));
const put = (g, x, y, c) => {
  if (x >= 0 && y >= 0 && x < W && y < H) g[y][x] = c;
};
const fillRect = (g, x, y, w, h, c) => {
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) put(g, x + i, y + j, c);
};

// Deterministic PRNG so the artwork never changes between runs.
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function text(g, s, x, y, scale, c, { gap = 1, mask = null } = {}) {
  let cx = x;
  for (const ch of s) {
    const rows = FONT[ch] || FONT[" "];
    rows.forEach((row, j) => {
      [...row].forEach((v, i) => {
        if (v !== "#") return;
        for (let b = 0; b < scale; b++) {
          for (let a = 0; a < scale; a++) {
            put(g, cx + i * scale + a, y + j * scale + b, c);
            if (mask) mask.add(`${cx + i * scale + a},${y + j * scale + b}`);
          }
        }
      });
    });
    cx += glyphW(ch) * scale + gap * scale;
  }
  return cx - gap * scale;
}

// Paint text as a mask first so drips and grit can work on its cells.
function heavyText(g, s, x, y, scale, c, { seed = 7, drips = true, grit = 0.006, shadow = null, maxDrip = 8 } = {}) {
  const tmp = grid();
  text(tmp, s, x, y, scale, "#");
  const r = rng(seed);
  if (shadow) {
    for (let j = 0; j < H; j++)
      for (let i = 0; i < W; i++)
        if (tmp[j][i] === "#") put(g, i + shadow.dx, j + shadow.dy, shadow.c);
  }
  for (let j = 0; j < H; j++)
    for (let i = 0; i < W; i++)
      if (tmp[j][i] === "#") g[j][i] = c;
  // grit: knock a few cells out of the stroke edges
  if (grit) {
    for (let j = 1; j < H - 1; j++)
      for (let i = 1; i < W - 1; i++) {
        if (tmp[j][i] !== "#") continue;
        const edge = tmp[j - 1][i] !== "#" || tmp[j + 1][i] !== "#" || tmp[j][i - 1] !== "#" || tmp[j][i + 1] !== "#";
        if (edge && r() < grit * 4) g[j][i] = " ";
      }
  }
  if (!drips) return;
  // drips: bottom edges of strokes, 3 cells wide, uneven length, rounded tip
  const spots = [];
  for (let j = 0; j < H - 1; j++)
    for (let i = 1; i < W - 3; i++)
      if ([0, 1, 2].every((a) => tmp[j][i + a] === "#" && tmp[j + 1][i + a] !== "#" && g[j][i + a] === c)) spots.push([i, j]);
  const used = [];
  const want = Math.max(3, Math.round(spots.length / (scale * 9)));
  let tries = 0;
  while (used.length < want && tries++ < 600 && spots.length) {
    const [i, j] = spots[Math.floor(r() * spots.length)];
    if (used.some(([ui]) => Math.abs(ui - i) < scale * 3)) continue;
    used.push([i, j]);
    const len = 3 + Math.floor(r() * (maxDrip - 2));
    for (let d = 1; d <= len; d++) {
      const tip = d === len;
      for (const a of tip ? [1] : [0, 1, 2]) if (g[j + d] && g[j + d][i + a] === " ") put(g, i + a, j + d, c);
    }
  }
}

function dither(g, x0, y0, x1, y1, c = "F", denseBand = 0) {
  for (let j = y0; j < y1; j += 2)
    for (let i = x0; i < x1; i += 2)
      if (((i / 2 + j / 2) % 2 === 0 || (i * 7 + j * 3) % 5 === 0 || (denseBand && (i + j) % 3 === 0)) && g[j][i] === " ") g[j][i] = c;
}

// Clear a halo of n cells around every cell of a char so dither backs off from lettering.
function halo(g, chars, n) {
  const hit = [];
  for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) if (chars.includes(g[j][i])) hit.push([i, j]);
  for (const [i, j] of hit)
    for (let b = -n; b <= n; b++)
      for (let a = -n; a <= n; a++) {
        const x = i + a, y = j + b;
        if (x >= 0 && y >= 0 && x < W && y < H && g[y][x] === "F") g[y][x] = " ";
      }
}

// ---------- banner ----------
// The subtitle is two lines of the same 5x7 font; it is too long for one line at this size.
const SUBTITLE = ["Grafischer Electribe-Leser", "und -Modifizierer plus Emulator"];
const NAME = "Kuhler's GELUMPE, Grafischer Electribe-Leser und -Modifizierer plus Emulator";

function banner() {
  const g = grid();
  dither(g, 0, 0, 36, H, "F");
  dither(g, 304, 0, W, H, "F");
  const head = resizedHead(76, 68);
  const headX = Math.floor((100 - head[0].length) / 2);
  const headY = Math.floor((H - head.length) / 2);
  fillRect(g, headX, headY, head[0].length, head.length, " ");
  head.forEach((row, y) => [...row].forEach((pixel, x) => {
    if (pixel === "#") put(g, headX + x, headY + y, "W");
  }));
  const x0 = 104;
  text(g, "Kuhler's", x0, 3, 2, "W");
  heavyText(g, "GELUMPE", x0, 19, 5, "A", { seed: 11, maxDrip: 5, shadow: { dx: 2, dy: 2, c: "F" } });
  SUBTITLE.forEach((line, n) => text(g, line, x0, 61 + n * 9, 1, "M"));
  return g;
}

// ---------- SVG ----------
function toSvg(g, name, theme) {
  const t = THEMES[theme];
  const path = (chars) => {
    let d = "";
    for (let j = 0; j < H; j++) {
      for (let i = 0; i < W; ) {
        if (!chars.includes(g[j][i])) { i++; continue; }
        let k = i;
        while (k < W && chars.includes(g[j][k])) k++;
        d += `M${i} ${j}h${k - i}v1h-${k - i}z`;
        i = k;
      }
    }
    return d;
  };
  const layer = (chars, fill, op) => {
    const d = path(chars);
    return d ? `<path fill="${fill}"${op ? ` fill-opacity="${op}"` : ""} d="${d}"/>\n` : "";
  };
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W * CELL}" height="${H * CELL}" role="img" aria-label="${name}">
<title>${name}</title>
<rect width="${W}" height="${H}" fill="${t.bg}"/>
<g shape-rendering="crispEdges">
${layer("F", t.accent, t.faint)}${layer("P", t.accent, t.pad)}${layer("M", t.accent, t.muted)}${layer("A", t.accent)}${layer("W", t.fg)}</g>
</svg>
`;
}

// ---------- main ----------
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "assets", "readme");
const argv = process.argv.slice(2);

if (argv.includes("--ascii")) {
  console.log(banner().map((r) => r.map((c) => ({ " ": " ", F: ",", P: ":", M: "+", A: "#", W: "o" })[c]).join("")).join("\n"));
  process.exit(0);
}

mkdirSync(out, { recursive: true });
const g = banner();
const files = ["dark", "light"].map((theme) => {
  const f = `banner-${theme}.svg`;
  writeFileSync(join(out, f), toSvg(g, NAME, theme));
  return f;
});
console.log(`wrote ${files.length} SVGs to ${out}`);

if (argv.includes("--png")) {
  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: W * CELL, height: H * CELL } });
  for (const f of files) {
    const svg = readFileSync(join(out, f), "utf8");
    await page.setContent(`<body style="margin:0;background:transparent">${svg}</body>`);
    await page.locator("svg").screenshot({ path: join(out, f.replace(".svg", ".png")) });
  }

  // Preview sheet: dark and light at full width and 640 px, on dark and white pages.
  const rel = (f) => pathToFileURL(join(out, f)).href;
  const panel = (cls, label, f, w) => `<div class="p ${cls}"><span>${label}</span><img src="${rel(f)}" width="${w}"></div>`;
  const html = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;padding:40px;background:#2b2d33;font:14px/1.3 -apple-system,Helvetica,Arial,sans-serif;color:#d8dbe0;width:1308px}
h1{font-size:20px;margin:0 0 24px}.p{padding:14px;margin-bottom:14px}.row{display:flex;gap:20px}.row .p{flex:0 0 auto}
.dark{background:#0d1117}.white{background:#fff;color:#222}span{display:block;font-size:12px;opacity:.7;margin-bottom:8px}img{display:block}
</style><h1>README banner, assets/readme/</h1>
${panel("dark", "1280 px, dark theme page (banner-dark)", "banner-dark.png", 1280)}
${panel("white", "1280 px, white page (banner-light)", "banner-light.png", 1280)}
<div class="row">
${panel("dark", "640 px, dark theme page (banner-dark)", "banner-dark.png", 640)}
${panel("white", "640 px, white page (banner-light)", "banner-light.png", 640)}
</div>`;
  const sheet = join(tmpdir(), "readme-banner-sheet.html");
  writeFileSync(sheet, html);
  const sp = await browser.newPage({ viewport: { width: 1388, height: 800 } });
  await sp.goto(pathToFileURL(sheet).href);
  await sp.waitForLoadState("load");
  await sp.screenshot({ path: join(out, "preview.png"), fullPage: true });
  await browser.close();
  console.log("wrote PNGs and preview.png");
}
