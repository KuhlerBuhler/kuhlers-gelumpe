#!/usr/bin/env node
/**
 * Check a release notes file (.github/workflows/release.yml, job "due"), or build the notes the app's Changelogs show.
 *
 *   node tools/release-notes.mjs check release-notes/1.3.5.md
 *   node tools/release-notes.mjs build
 *
 * `check` exits 1 and says what is missing when the German part or the English part (under "## English") is empty or
 * absent. `build` writes data/release-notes.mjs from every release-notes/<version>.md, newest first.
 */
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { appNotes, checkNotes, compareVersions, parseNotes } from "./release-lib.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const NOTES_DIR = join(ROOT, "release-notes");
export const NOTES_MODULE = join(ROOT, "data", "release-notes.mjs");

/** The source of data/release-notes.mjs for the notes files in `dir`. */
export function notesModule(dir = NOTES_DIR) {
  const versions = readdirSync(dir).map(f => /^(\d+\.\d+\.\d+)\.md$/.exec(f)?.[1]).filter(Boolean).sort(compareVersions).reverse();
  const entries = versions.map(version => {
    const { de, en } = parseNotes(readFileSync(join(dir, `${version}.md`), "utf8"));
    return { version, de: appNotes(de), en: en === null ? null : appNotes(en) };
  });
  return `/**
 * The release notes of every version, for the app's Changelogs (site/app/changelog.mjs). Made from release-notes/ by
 * \`node tools/release-notes.mjs build\`; do not edit by hand. \`en\` is null for versions that had German notes only.
 */
export const RELEASE_NOTES = Object.freeze(${JSON.stringify(entries, null, 2)});
`;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [command, file] = process.argv.slice(2);
  if (command === "build") {
    writeFileSync(NOTES_MODULE, notesModule());
    console.log(`${NOTES_MODULE.slice(ROOT.length + 1)} geschrieben`);
    process.exit(0);
  }
  if (command !== "check" || !file) {
    console.error("Aufruf: node tools/release-notes.mjs check <Datei> | build");
    process.exit(2);
  }
  const problems = checkNotes(readFileSync(file, "utf8"));
  for (const p of problems) console.error(`${file}: ${p}`);
  process.exit(problems.length ? 1 : 0);
}
