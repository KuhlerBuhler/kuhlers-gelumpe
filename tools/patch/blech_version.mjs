#!/usr/bin/env node
/**
 * Build the patch blech-version: the release version as text ("BLECH 1.3.7", NUL padded to 16 bytes) at 0xC014FCF0, where
 * the page BLECH > VERSION reads it (VERSION_TEXT in tools/patch/script_menu.s). The 16 bytes are FF in all three 2.02 builds,
 * in the run 0xC0148880..0xC0150000 in front of the init-pattern code, and nothing reads them at the start. Data only, no code;
 * one file for the red set and one for the blue, with the same bytes. tools/set-version.mjs rebuilds both with every version.
 *
 *   node tools/patch/blech_version.mjs [version]      (default: the version in package.json)
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const VERSION_AT = 0xC014FCF0;
export const VERSION_FILE = VERSION_AT - 0xC0000000 + 0x100;
export const VERSION_WIDTH = 16;
/** The two files and the builds each is for. */
export const VERSION_PATCHES = [
  { path: "data/patches/blech-version.json", builds: ["hacktribe", "stock"] },
  { path: "data/patches/blech-version-synth.json", builds: ["synth"] },
];

/** The patch for one version (x.y.z) and its builds as the JSON text its file holds. */
export function versionPatch(version, builds = VERSION_PATCHES[0].builds) {
  if (!/^\d+\.\d+\.\d+$/.test(version)) throw new Error(`not a version: ${version}`);
  const text = `BLECH ${version}`;
  if (text.length >= VERSION_WIDTH) throw new Error(`${text} does not fit ${VERSION_WIDTH} bytes with its NUL`);
  const bytes = Buffer.alloc(VERSION_WIDTH);
  bytes.write(text, "latin1");
  const patch = {
    format: "gelumpe-patch",
    version: 1,
    id: "blech-version",
    name: "BLECH-Version im Menü",
    builds,
    changes: [{
      file: VERSION_FILE,
      bytes: bytes.toString("hex"),
      expect: createHash("sha256").update(Buffer.alloc(VERSION_WIDTH, 0xff)).digest("hex"),
      note: `${text}: BLECH > VERSION shows it`,
    }],
    ram: [],
  };
  return `${JSON.stringify(patch, null, 1)}\n`;
}

/** Writes both files for a version; returns their paths. */
export function writeVersionPatches(version) {
  return VERSION_PATCHES.map(({ path, builds }) => {
    const out = fileURLToPath(new URL(`../../${path}`, import.meta.url));
    writeFileSync(out, versionPatch(version, builds));
    return out;
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const version = process.argv[2] ?? JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8")).version;
  for (const out of writeVersionPatches(version.replace(/^v/, ""))) console.log(`wrote ${out}`);
}
