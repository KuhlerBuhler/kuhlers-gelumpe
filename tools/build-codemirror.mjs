#!/usr/bin/env node
/**
 * Rebuild the vendored CodeMirror bundle:
 *
 *   npm install && npm run build:codemirror
 *
 * Bundles tools/codemirror-entry.mjs into site/vendor/codemirror.mjs (one minified ES module, no
 * network at run time, so the site works offline in the app) and writes the licence texts of
 * every package that went in next to it. esbuild and the CodeMirror packages are devDependencies:
 * they are needed to rebuild, never to run the editor or the tests.
 */
import { build } from "esbuild";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ENTRY = join(ROOT, "tools/codemirror-entry.mjs");
const OUT_DIR = join(ROOT, "site/vendor");
const OUT = join(OUT_DIR, "codemirror.mjs");
const LICENCES = join(OUT_DIR, "codemirror.LICENSE.txt");

mkdirSync(OUT_DIR, { recursive: true });
const result = await build({
  entryPoints: [ENTRY],
  bundle: true,
  format: "esm",
  minify: true,
  target: "es2022",
  legalComments: "none",
  metafile: true,
  write: false,
  outfile: OUT,
  logLevel: "warning",
});

const entryHash = createHash("sha256").update(readFileSync(ENTRY)).digest("hex").slice(0, 16);
const packages = new Map();
for (const input of Object.keys(result.metafile.inputs)) {
  const m = /^(.*node_modules\/((?:@[^/]+\/)?[^/]+))\//.exec(input);
  if (m) packages.set(m[2], join(ROOT, m[1]));
}
const sections = [];
for (const [name, dir] of [...packages].sort(([a], [b]) => a.localeCompare(b))) {
  const info = JSON.parse(readFileSync(join(dir, "package.json"), "utf8"));
  const file = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"].map(f => join(dir, f)).find(existsSync);
  if (!file) throw new Error(`${name} has no licence file to ship with the bundle`);
  sections.push(`${name} ${info.version} (${info.license})\n${"-".repeat(40)}\n${readFileSync(file, "utf8").trim()}\n`);
}

const header = `// CodeMirror 6 for the plugin editor: ${[...packages.keys()].sort().join(", ")}. MIT, see codemirror.LICENSE.txt.\n// Built by tools/build-codemirror.mjs from tools/codemirror-entry.mjs (sha256 ${entryHash}). Do not edit.\n`;
const code = result.outputFiles[0].text;
writeFileSync(OUT, header + code);
writeFileSync(LICENCES, `Licences of the packages bundled into codemirror.mjs.\nRebuild with: npm run build:codemirror\n\n${sections.join("\n")}`);
console.log(`${OUT.slice(ROOT.length + 1)}: ${((header.length + code.length) / 1024).toFixed(1)} KiB, ${packages.size} packages`);
