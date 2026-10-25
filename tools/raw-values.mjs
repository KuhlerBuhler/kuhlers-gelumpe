#!/usr/bin/env node
/**
 * Finds raw design values in the editor's own code that must be tokens (DESIGN.md):
 *   CSS  colors (hex, rgb(), hsl(), also as a var() fallback), px radii, literal font sizes,
 *        gradients, and spacing (padding, margin, gap) other than 0, 1px and 2px
 *   JS   colors and literal lengths in inline styles
 * Ported from the Interface (tools/raw-values.mjs). site/design/ is the Interface's copy and is not scanned.
 * A value that is not design, such as a pixel of the device's screen, carries `raw-ok: <why>` on its line or the line above.
 *
 * Usage: node tools/raw-values.mjs [file ...]   (exit 1 on hits)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE = path.join(ROOT, "site");
const SKIP = new Set(["design", "vendor", "fonts"]);

const COLOR = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?)\(/i;
const LENGTH = /(?<![\w-])-?\d*\.?\d+(?:px|rem|em)\b/g;
// 1px and 2px are borders and the gap between a line and its sub line (DESIGN.md, scale).
const allowedSpace = (v) => /^-?(?:1|2)px$/.test(v);

const DECLARATION_RULES = [
  { kind: "color", test: (prop, value) => !prop.startsWith("--") && COLOR.test(value) },
  { kind: "radius", test: (prop, value) => /radius$/.test(prop) && /\d+(?:\.\d+)?px/.test(value) },
  { kind: "font-size", test: (prop, value) => prop === "font-size" && /\d(?:px|rem|em)\b/.test(value) },
  { kind: "gradient", test: (prop, value) => !/^(?:-webkit-)?mask/.test(prop) && /gradient\(/i.test(value) },
  {
    kind: "spacing",
    test: (prop, value) => /^(?:padding|margin|gap|row-gap|column-gap)(?:-|$)/.test(prop)
      && (value.replace(/var\([^)]*\)/g, "").match(LENGTH) || []).some((v) => !allowedSpace(v)),
  },
];

/** Hits in CSS source, one per offending declaration, with its line. */
export function findInCss(source) {
  const hits = [];
  const code = source.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, " "));
  // A declaration: a property, a colon and a value up to ; or }. Selectors never end in a colon followed by a value and ;.
  const re = /(^|[{;\s])(--[\w-]+|[a-z-]+)\s*:\s*([^;{}]+)(?=[;}])/g;
  for (const m of code.matchAll(re)) {
    const prop = m[2].toLowerCase();
    const value = m[3].trim();
    // a:hover { … } is a selector; a value never starts with a pseudo class name followed by {.
    const line = code.slice(0, m.index + m[1].length).split("\n").length;
    for (const { kind, test } of DECLARATION_RULES) {
      if (test(prop, value)) hits.push({ line, kind, text: `${prop}: ${value}`.slice(0, 140) });
    }
  }
  return hits;
}

/** Hits in JS: a string that is a color, or an inline style set to a literal length or color. */
export function findInJs(source) {
  const hits = [];
  source.split("\n").forEach((line, i) => {
    const code = line.replace(/^\s*\/\/.*$/, "").replace(/\s\/\/\s.*$/, "");
    if (/["'`]\s*(?:#[0-9a-f]{3,8}|(?:rgba?|hsla?)\([^"'`]*)\s*["'`]/i.test(code)) hits.push({ line: i + 1, kind: "color", text: line.trim().slice(0, 140) });
    if (/\.style\.(?:padding|margin|gap|fontSize|borderRadius)\w*\s*=\s*["'`][^"'`]*\d(?:px|rem|em)/.test(code)
      || /style\s*=\s*\\?["'][^"']*(?:padding|margin|gap|font-size|border-radius)[^"']*\d(?:px|rem|em)/.test(code)) {
      hits.push({ line: i + 1, kind: "inline-length", text: line.trim().slice(0, 140) });
    }
  });
  return hits;
}

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return SKIP.has(e.name) ? [] : walk(p);
    return /\.(css|m?js|html)$/.test(e.name) ? [p] : [];
  });
}

export function scan(files = walk(SITE)) {
  const hits = [];
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    let found;
    if (file.endsWith(".css")) found = findInCss(source);
    else if (file.endsWith(".html")) {
      // Only the style blocks and style attributes of a page carry design values.
      found = [...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].flatMap((m) => {
        const offset = source.slice(0, m.index).split("\n").length - 1;
        return findInCss(m[1]).map((h) => ({ ...h, line: h.line + offset }));
      }).concat(findInJs(source).filter((h) => h.kind === "inline-length"));
    } else found = findInJs(source);
    const lines = source.split("\n");
    const excused = (n) => /raw-ok:/.test(lines[n - 1] || "") || /raw-ok:/.test(lines[n - 2] || "");
    for (const h of found) if (!excused(h.line)) hits.push({ file: path.relative(ROOT, file), ...h });
  }
  return hits;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2).map((f) => path.resolve(f));
  const hits = scan(args.length ? args : undefined);
  for (const h of hits) console.log(`${h.file}:${h.line}  [${h.kind}]  ${h.text}`);
  console.log(hits.length ? `✗ ${hits.length} raw values, use a token from site/design/root.min.css` : "✓ No raw values");
  process.exit(hits.length ? 1 : 0);
}
