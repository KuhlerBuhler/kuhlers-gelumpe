#!/usr/bin/env node
/**
 * Put a release version into the files the app takes it from, and into the patch
 * blech-version (both files) the device shows it from, in the working tree only. tools/release.mjs commits them as "Release vX.Y.Z".
 *
 *   node tools/set-version.mjs 1.2.3      (a leading v is fine)
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { writeVersionPatches } from "./patch/blech_version.mjs";

const version = (process.argv[2] || "").replace(/^v/, "");
if (!/^\d+\.\d+\.\d+$/.test(version)) {
  console.error("Aufruf: node tools/set-version.mjs 1.2.3");
  process.exit(1);
}
const file = rel => fileURLToPath(new URL(rel, import.meta.url));
const edit = (rel, fn) => {
  const path = file(rel);
  const before = readFileSync(path, "utf8");
  const after = fn(before);
  if (after === before && !before.includes(version)) throw new Error(`${rel}: keine Version gefunden`);
  writeFileSync(path, after);
};
edit("../package.json", s => s.replace(/("version": ")[^"]+/, `$1${version}`));
edit("../src-tauri/tauri.conf.json", s => s.replace(/("version": ")[^"]+/, `$1${version}`));
edit("../src-tauri/Cargo.toml", s => s.replace(/^version = ".*"$/m, `version = "${version}"`));
edit("../src-tauri/Cargo.lock", s => s.replace(/(name = "kuhlers-gelumpe"\r?\nversion = ")[^"]+/, `$1${version}`));
writeVersionPatches(version);
console.log(`Version ${version}`);
