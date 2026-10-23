#!/usr/bin/env node
/**
 * Builds Blechy's plugin source from his frame tables (data/script/blechy-art.mjs) and his behaviour
 * (data/script/blechy-logic.mjs). A frame becomes bitmaps: one array of display columns for each picture, drawn
 * with korg.display.bitmap (data/script/contract.mjs says how a slot maps to pixels).
 *
 * He is built into BLECH, so the build also compiles the source, probes it with the recorded inputs (it must come out
 * clean, every line run), marks the block as probed and writes it as hex text in data/script/blechy-block.hex (64 digits to a line): the patch
 * script-runtime (tools/patch/script_hooks.py) puts exactly these bytes into the firmware image.
 *
 *   node tools/blechy-build.mjs            write data/script/blechy-source.mjs, the block, the test fixtures and the preview picture
 *   node tools/blechy-build.mjs --check    exit 1 when one of them is not what the tables make (the test runs this)
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { FRAMES, FRAME_ORDER, SPRITE_DIR } from "../data/script/blechy-art.mjs";
import { BLECHY_LOGIC } from "../data/script/blechy-logic.mjs";
import { API_BY_NAME } from "../data/script/contract.mjs";
import { KEY_NAMES, LED_NAMES } from "../data/script/names.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { markProbed } from "../src/script/blob.mjs";
import { probe } from "../src/script/sim.mjs";
import { blechyInputs } from "../test/support/blechy-inputs.mjs";
import { pixelPng, readPng, sheet } from "./blechy-png.mjs";
import { outlined } from "../src/blechy-outline.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const WIDTH = 128;
const HEIGHT = 64;
/** A picture is a record in the block's data section: 4 bytes and its slots from the first to the last lit one, padded to 4. */
const RECORD_BYTES = 4;
const CALL_BYTES = 20;
const BITMAP = API_BY_NAME.get("korg.display.bitmap");

/** The frames of the art table with their picture: { sprite, x, y, rows }. */
export function loadFrames() {
  const sprites = {};
  // The sprites are filled; on the display he is drawn as the loading animation draws him, the body as its outline.
  const rowsOf = name => (sprites[name] ??= outlined(readPng(readFileSync(root + SPRITE_DIR + `blechy-${name}.png`)).map(r => [...r].map(c => c === "#")))
    .map(r => r.map(lit => (lit ? "#" : ".")).join("")));
  return Object.fromEntries(FRAME_ORDER.map(name => [name, { ...FRAMES[name], rows: rowsOf(FRAMES[name].sprite) }]));
}

/** A frame on the whole display, rows of "#" and ".", clipped at the edges. */
function onDisplay(frame) {
  const grid = Array.from({ length: HEIGHT }, () => Array(WIDTH).fill("."));
  frame.rows.forEach((row, y) => [...row].forEach((c, x) => {
    const X = frame.x + x;
    const Y = frame.y + y;
    if (c === "#" && X >= 0 && X < WIDTH && Y >= 0 && Y < HEIGHT) grid[Y][X] = "#";
  }));
  return grid;
}

const rowsOfGrid = grid => grid.map(r => r.join(""));

/**
 * The slots of the lit pixels of a picture on the display, in the layout of korg.display.bitmap: the box around the lit
 * pixels, cut into bands of 8 rows, one slot a column with the top pixel in bit 0. The bands may start up to 7 rows above the
 * box, whichever start leaves the fewest slots that are not 0 (those are what costs code).
 */
export function slotsOf(rows) {
  const lit = [];
  rows.forEach((row, y) => [...row].forEach((c, x) => { if (c === "#") lit.push([x, y]); }));
  if (!lit.length) return null;
  const x0 = Math.min(...lit.map(p => p[0]));
  const x1 = Math.max(...lit.map(p => p[0]));
  const top = Math.min(...lit.map(p => p[1]));
  const bottom = Math.max(...lit.map(p => p[1]));
  const width = x1 - x0 + 1;
  let best = null;
  for (let lift = 0; lift < 8 && top - lift >= -64; lift++) {
    const y0 = top - lift;
    const bands = Math.ceil((bottom - y0 + 1) / 8);
    const slots = Array(width * bands).fill(0);
    for (const [x, y] of lit) slots[Math.floor((y - y0) / 8) * width + (x - x0)] |= 1 << ((y - y0) % 8);
    const used = slots.filter(v => v).length;
    if (!best || used < best.used || (used === best.used && slots.length < best.slots.length)) best = { x: x0, y: y0, width, slots, used };
  }
  return best;
}

const bitmapBytes = b => {
  const first = b.slots.findIndex(v => v), last = b.slots.findLastIndex(v => v);
  return CALL_BYTES + (first < 0 ? 0 : RECORD_BYTES + ((last - first + 4) & ~3));
};
const bitmapFuel = b => BITMAP.cost + b.slots.length * BITMAP.perItem;

/** The array declaration of a picture, one line a band. */
function arrayOf(name, b) {
  const bands = [];
  for (let i = 0; i < b.slots.length; i += b.width) bands.push(`  ${b.slots.slice(i, i + b.width).join(", ")}`);
  return `const ${name} = [\n${bands.join(",\n")}\n];`;
}

const camel = name => name[0].toUpperCase() + name.slice(1);
const constant = name => `F_${name.replace(/\d+$/, "").toUpperCase()}`;
const upper = name => name.replace(/([a-z])([A-Z])/g, "$1_$2").toUpperCase();

/** A table position plus the offset the logic passes, as source text. */
const shift = (v, name) => (v === 0 ? name : v > 0 ? `${name} + ${v}` : `${name} - ${-v}`);

const same = (grids, x, y) => grids.every(g => g[y][x] === grids[0][y][x]);

/** The frames of one family: what they share (base), where they differ (the box), and what each adds. */
function family(names, grids) {
  const all = names.map(n => grids[n]);
  const common = all[0].map((row, y) => row.map((_, x) => (all.every(g => g[y][x] === "#") ? "#" : ".")));
  const differ = [];
  for (let y = 0; y < HEIGHT; y++) for (let x = 0; x < WIDTH; x++) if (!same(all, x, y)) differ.push([x, y]);
  const box = differ.length ? { x: Math.min(...differ.map(d => d[0])), y: Math.min(...differ.map(d => d[1])), x2: Math.max(...differ.map(d => d[0])), y2: Math.max(...differ.map(d => d[1])) } : null;
  const core = common.map((row, y) => row.map((c, x) => (box && x >= box.x && x <= box.x2 && y >= box.y && y <= box.y2 ? c : ".")));
  return { common, core, box };
}

/** The frame functions and the drawFrame that picks them. Frames of a family draw their shared part once. */
function frameBlock(frames) {
  const grids = Object.fromEntries(FRAME_ORDER.map(name => [name, onDisplay(frames[name])]));
  const families = {};
  for (const name of FRAME_ORDER) if (frames[name].family) (families[frames[name].family] ??= []).push(name);
  const out = ["// The frame numbers and the pictures below are made from data/script/blechy-art.mjs by tools/blechy-build.mjs."];
  const seen = new Set();
  FRAME_ORDER.forEach((name, i) => {
    const c = constant(name);
    if (!seen.has(c)) { seen.add(c); out.push(`const ${c} = ${i};`); }
  });
  const lit = rowsOfGrid(grids.idle).flatMap(r => [...r].flatMap((ch, i) => (ch === "#" ? [i] : [])));
  const walkRight = Math.max(...FRAME_ORDER.filter(n => !n.startsWith("flail")).flatMap(n => rowsOfGrid(grids[n]).flatMap(r => [...r].flatMap((ch, i) => (ch === "#" ? [i] : [])))));
  out.push(`const FIG_LEFT = ${Math.min(...lit)};`, `const FIG_RIGHT = ${Math.max(...lit)};`, `const WALK_RIGHT = ${walkRight};`, "");
  const report = [];
  const index = name => FRAME_ORDER.indexOf(name);
  const test = (names, v) => names.map(n => `${v} == ${index(n)}`).join(" || ");
  const arrays = new Map();
  /** A picture as its array and a function that draws it; nothing lit gives an empty function, and an array that is there already is used again. */
  const picture = (name, rows, label) => {
    const b = slotsOf(rows);
    report.push({ name: label, slots: b?.slots.length ?? 0, used: b?.used ?? 0, bytes: b ? bitmapBytes(b) : 0, fuel: b ? bitmapFuel(b) : 0 });
    if (!b) return `function ${name}(ox, oy) {\n}`;
    const key = JSON.stringify(b);
    const shared = arrays.get(key);
    const data = shared ?? `P_${upper(name.replace(/^frame/, ""))}`;
    arrays.set(key, data);
    return `${shared ? "" : `${arrayOf(data, b)}\n\n`}function ${name}(ox, oy) {\n  korg.display.bitmap(${data}, ${shift(b.x, "ox")}, ${shift(b.y, "oy")}, ${b.width});\n}`;
  };
  const parts = [];
  const made = new Set();
  for (const [fam, names] of Object.entries(families)) {
    const f = family(names, grids);
    const F = camel(fam);
    out.push(picture(`frame${F}Base`, rowsOfGrid(f.common), `${fam} base`), "", picture(`frame${F}Core`, rowsOfGrid(f.core), `${fam} core`), "");
    for (const name of names) {
      const rest = grids[name].map((r, y) => r.map((c, x) => (c === "#" && f.common[y][x] !== "#" ? "#" : ".")));
      out.push(picture(`frame${camel(name)}`, rowsOfGrid(rest), name), "");
      made.add(name);
    }
    const b = f.box;
    parts.push(`if (${test(names, "f")}) {
    if (${test(names, "last")}) {
      korg.display.clearRect(${shift(b.x, "ox")}, ${shift(b.y, "oy")}, ${b.x2 - b.x + 1}, ${b.y2 - b.y + 1});
      frame${F}Core(ox, oy);
    } else {
      korg.display.clear();
      frame${F}Base(ox, oy);
    }
    ${names.map((n, i) => `${i ? "else " : ""}if (f == ${index(n)}) frame${camel(n)}(ox, oy);`).join("\n    ")}
  }`);
  }
  const rest = FRAME_ORDER.filter(n => !made.has(n));
  for (const name of rest) out.push(picture(`frame${camel(name)}`, rowsOfGrid(grids[name]), name), "");
  const whole = rest.map((n, i) => `${i ? "else " : ""}if (f == ${index(n)}) frame${camel(n)}(ox, oy);`).join("\n    ");
  const dispatch = `${parts.join(" else ")}${rest.length ? ` else {\n    korg.display.clear();\n    ${whole}\n  }` : ""}`;
  return { text: out.join("\n").trimEnd(), report, dispatch };
}

/** The firmware block of a source: compiled, probed with Blechy's recorded inputs, marked as probed. */
export function blockOf(source) {
  const built = compile(source, { name: "Blechy" });
  if (!built.ok) throw new Error(built.errors.map(formatError).join("\n"));
  const result = probe(built.blob, blechyInputs());
  if (!result.ok || result.lines.missing.length) throw new Error(`the probe is not clean: ${JSON.stringify({ faults: result.faults, missing: result.lines.missing, text: result.lines.missing.map(n => source.split("\n")[n - 1]) })}`);
  return markProbed(built.blob);
}

/** Bytes as hex text, 64 digits to a line. */
const hexLines = bytes => `${Buffer.from(bytes).toString("hex").match(/.{1,64}/g).join("\n")}\n`;

/** Everything the build makes, as { path: bytes or text }, and the per frame cost report. */
export function build() {
  const frames = loadFrames();
  const { text, report, dispatch } = frameBlock(frames);
  const source = BLECHY_LOGIC.replace("// @@FRAMES@@", text).replace("// @@DISPATCH@@", dispatch);
  const numbered = source
    .replace(/korg\.key\.([A-Z][A-Z0-9_]*)/g, (all, n) => String(KEY_NAMES.find(k => k.name === n)?.value ?? all))
    .replace(/korg\.led\.([A-Z][A-Z0-9_]*)/g, (all, n) => String(LED_NAMES.find(k => k.name === n)?.value ?? all));
  const escaped = source.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$\{/g, "\\${");
  const preview = pixelPng(sheet(FRAME_ORDER.map(name => frames[name].rows), 2), 4, 4);
  return {
    files: {
      "data/script/blechy-source.mjs": `/** Blechy's plugin source. Made by tools/blechy-build.mjs from blechy-art.mjs and blechy-logic.mjs; do not edit it here. */\nexport const BLECHY_SOURCE = \`${escaped}\`;\n`,
      "data/script/blechy-block.hex": hexLines(blockOf(source)),
      "test/fixtures/scripts/blechy.js": source,
      "test/fixtures/scripts/numbers/blechy.js": numbered,
      "docs/images/blechy-frames.png": preview,
    },
    report,
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { files, report } = build();
  const check = process.argv.includes("--check");
  let stale = 0;
  for (const [path, data] of Object.entries(files)) {
    const file = root + path;
    const now = existsSync(file) ? readFileSync(file) : null;
    const want = Buffer.from(data);
    if (check) {
      if (!now || !now.equals(want)) { stale++; console.error(`stale: ${path}`); }
    } else {
      writeFileSync(file, want);
    }
  }
  for (const r of report) console.log(`${r.name.padEnd(11)} ${String(r.slots).padStart(4)} slots, ${String(r.used).padStart(4)} not 0, about ${String(r.bytes).padStart(5)} bytes of code and data, ${String(r.fuel).padStart(4)} fuel`);
  if (stale) process.exit(1);
}
