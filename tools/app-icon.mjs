// Generates the three app icon variants in assets/app-icon/ as SVG.
// Everything sits on a 64 x 64 cell grid (1 cell = 8 units of the 512 viewBox)
// so the icon keeps the 1-bit look of the BLECH splash. Own artwork, no Korg assets.
//
//   node tools/app-icon.mjs            write the SVGs
//   node tools/app-icon.mjs --ascii    print the grids instead

import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const N = 64;
const CELL = 8;
const COL = { bg: "#0a0a0b", g: "#9ec3d1", eye: "#fafafa" };

const grid = () => Array.from({ length: N }, () => new Array(N).fill(" "));
const inRR = (px, py, x, y, w, h, r) => {
  if (px < x || py < y || px >= x + w || py >= y + h) return false;
  const cx = Math.min(Math.max(px, x + r), x + w - r);
  const cy = Math.min(Math.max(py, y + r), y + h - r);
  return (px - cx) ** 2 + (py - cy) ** 2 <= r * r;
};

// Heavy G with a drip. x,y,w,h in cells, t = stroke, bt = bar thickness.
function drawG(g, { x, y, w, h, t, bt, r, gapTop, barY, drip = true }) {
  const ri = Math.max(r - t, 3);
  for (let j = 0; j < h; j++) {
    for (let i = 0; i < w; i++) {
      const px = i + 0.5, py = j + 0.5;
      const ring = inRR(px, py, 0, 0, w, h, r) && !inRR(px, py, t, t, w - 2 * t, h - 2 * t, ri);
      const gap = i >= w / 2 && j >= gapTop && j < barY;
      const bar = i >= w / 2 - 1 && j >= barY && j < barY + bt && i < w;
      if ((ring && !gap) || bar) g[y + j][x + i] = "G";
    }
  }
  if (drip) {
    // two drips under the bottom arm: one long, one short
    const bx = x + Math.round(w * 0.3), by = y + h;
    for (let j = 0; j < 4; j++) for (let i = 0; i < 3; i++) g[by + j][bx + i] = "G";
    g[by + 4][bx] = "G"; g[by + 4][bx + 1] = "G";
    const sx = x + Math.round(w * 0.58);
    for (let j = 0; j < 2; j++) for (let i = 0; i < 3; i++) g[by + j][sx + i] = "G";
  }
}

// Terror eye: ring, square pupil, small lid tab under it.
function drawEye(g, { cx, cy, R, th, pupil, lid = true, halo = 0, haloOnly = false }) {
  const paint = (v, d0, d1) => {
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const d = Math.hypot(i + 0.5 - cx, j + 0.5 - cy);
      if (d >= d0 && d <= d1) g[j][i] = v;
    }
  };
  if (halo) paint("B", 0, R + halo);
  if (halo && lid) {
    for (let j = Math.floor(cy + R - 1); j < cy + R + 4 + halo; j++)
      for (let i = Math.floor(cx - R * 0.7 - halo); i < cx + R * 0.7 + halo; i++) g[j][i] = "B";
  }
  if (haloOnly) return;
  paint(" ", 0, R);
  if (halo) paint("B", 0, R);
  paint("E", R - th, R);
  const p0 = Math.round(cx - pupil / 2), q0 = Math.round(cy - pupil / 2);
  for (let j = 0; j < pupil; j++) for (let i = 0; i < pupil; i++) g[q0 + j][p0 + i] = "E";
  if (lid) {
    const y0 = Math.round(cy + R - 0.5);
    const rows = [[0.62], [0.52], [0.52]];
    rows.forEach(([k], n) => {
      const half = Math.round(R * k);
      const a = Math.round(cx - half), b = Math.round(cx + half);
      for (let i = a; i < b; i++) {
        const edge = i === a || i === b - 1 || n === rows.length - 1;
        g[y0 + n][i] = edge ? "E" : g[y0 + n][i] === "B" ? "B" : " ";
      }
    });
  }
}

// Faint dither dots on a 2-cell pitch, only where nothing else sits.
function dither(g, x0, y0, x1, y1) {
  for (let j = y0; j < y1; j += 2) {
    for (let i = x0; i < x1; i += 2) {
      // loose staggered pattern like the splash backdrop
      if ((i / 2 + j / 2) % 2 === 0 || (i * 7 + j * 3) % 5 === 0) g[j][i] = g[j][i] === " " ? "D" : g[j][i];
    }
  }
}

const variants = {
  // A: eyes above the G, clean
  a: () => {
    const g = grid();
    drawG(g, { x: 13, y: 28, w: 38, h: 28, t: 8, bt: 7, r: 13, gapTop: 10, barY: 15 });
    drawEye(g, { cx: 22, cy: 15.5, R: 9, th: 2, pupil: 3 });
    drawEye(g, { cx: 42, cy: 15.5, R: 9, th: 2, pupil: 3 });
    return g;
  },
  // D: A plus dither dots, kept to the side bands so G and eyes stay clean
  d: () => {
    const g = grid();
    dither(g, 4, 6, 60, 58);
    for (let j = 0; j < N; j++) for (let i = 11; i < 53; i++) g[j][i] = " ";
    drawG(g, { x: 13, y: 28, w: 38, h: 28, t: 8, bt: 7, r: 13, gapTop: 10, barY: 15 });
    drawEye(g, { cx: 22, cy: 15.5, R: 9, th: 2, pupil: 3 });
    drawEye(g, { cx: 42, cy: 15.5, R: 9, th: 2, pupil: 3 });
    return g;
  },
  // B: big G, the eyes sit inside its counter
  b: () => {
    const g = grid();
    drawG(g, { x: 9, y: 5, w: 46, h: 49, t: 10, bt: 9, r: 20, gapTop: 15, barY: 28 });
    drawEye(g, { cx: 25.5, cy: 23.5, R: 5.5, th: 1.5, pupil: 2, lid: false });
    drawEye(g, { cx: 38.5, cy: 23.5, R: 5.5, th: 1.5, pupil: 2, lid: false });
    return g;
  },
  // C: dithered backdrop, G with the eyes peeking over its top edge
  c: () => {
    const g = grid();
    dither(g, 4, 6, 60, 58);
    drawG(g, { x: 10, y: 24, w: 44, h: 32, t: 9, bt: 8, r: 15, gapTop: 12, barY: 17 });
    const eyes = [23, 41].map((cx) => ({ cx, cy: 13, R: 8.5, th: 2, pupil: 3, halo: 2 }));
    eyes.forEach((e) => drawEye(g, { ...e, haloOnly: true }));
    for (let j = 18; j < 27; j++) for (let i = 23; i < 41; i++) if (g[j][i] === "G") g[j][i] = "B";
    eyes.forEach((e) => drawEye(g, e));
    return g;
  },
};

function toSvg(g, title) {
  const path = (ch) => {
    let d = "";
    for (let j = 0; j < N; j++) {
      for (let i = 0; i < N; ) {
        if (g[j][i] !== ch) { i++; continue; }
        let k = i;
        while (k < N && g[j][k] === ch) k++;
        d += `M${i * CELL} ${j * CELL}h${(k - i) * CELL}v${CELL}h${-(k - i) * CELL}z`;
        i = k;
      }
    }
    return d;
  };
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
<title>${title}</title>
<rect width="512" height="512" rx="112" fill="${COL.bg}"/>
<g shape-rendering="crispEdges">
<path fill="${COL.g}" fill-opacity=".3" d="${path("D")}"/>
<path fill="${COL.g}" d="${path("G")}"/>
<path fill="${COL.bg}" d="${path("B")}"/>
<path fill="${COL.eye}" d="${path("E")}"/>
</g>
</svg>
`;
}

const names = { a: "GELUMPE icon A, eyes above the G", b: "GELUMPE icon B, eyes inside the G", c: "GELUMPE icon C, G with eyes and dither backdrop", d: "GELUMPE icon D, eyes above the G on a dither backdrop" };
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "assets", "app-icon");

if (process.argv.includes("--ascii")) {
  for (const [k, f] of Object.entries(variants)) {
    console.log(`--- ${k}`);
    console.log(f().map((r) => r.map((c) => ({ " ": " ", G: "#", E: "o", B: ".", D: "," })[c]).join("")).join("\n"));
  }
} else {
  mkdirSync(out, { recursive: true });
  for (const [k, f] of Object.entries(variants)) writeFileSync(join(out, `variant-${k}.svg`), toSvg(f(), names[k]));
}
