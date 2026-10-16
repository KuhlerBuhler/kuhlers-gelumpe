#!/usr/bin/env node
/**
 * Assemble the static site into dist/, the frontend the app (Tauri) ships.
 *
 * Same layout as tools/serve.mjs. Only what the page needs goes in: no
 * tests, no tools, and never a firmware image.
 */
import { cpSync, mkdirSync, rmSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ROUTES } from "./site-routes.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const DIST = join(ROOT, "dist");
// Korg data never goes out, whatever ends up in the working tree.
const FORBIDDEN = /\.(vsb|syx|e2sallpat|e2spat|all|wav|aif|aiff)$/i;
// Node-only modules stay out of the page, and so do the design system's own
// documents: COMPONENTS.md is an overview of every component, which is what
// the editor must not publish. Of assets/blechy only the patch and the picture go out, not the sounds.
const SKIP = new Set(["src/node.mjs", "src/webmidi.mjs"]);
const SKIP_PATTERN = /^(site\/design\/.*\.md|assets\/blechy\/.*\.(mp3|bin)|docs\/(?!plugins\.md$).+)$/;

rmSync(DIST, { recursive: true, force: true });
for (const [prefix, dir] of ROUTES) {
  const to = join(DIST, prefix);
  mkdirSync(to, { recursive: true });
  cpSync(join(ROOT, dir), to, {
    recursive: true,
    filter: src => {
      const rel = src.slice(ROOT.length + 1);
      if (SKIP.has(rel) || SKIP_PATTERN.test(rel)) return false;
      if (FORBIDDEN.test(src)) throw new Error(`refusing to publish ${rel}`);
      return true;
    },
  });
}

let count = 0;
const walk = d => readdirSync(d).forEach(n => {
  const p = join(d, n);
  statSync(p).isDirectory() ? walk(p) : count++;
});
walk(DIST);
console.log(`dist/: ${count} files`);
