#!/usr/bin/env node
/**
 * Check a release notes file (.github/workflows/release.yml, job "due").
 *
 *   node tools/release-notes.mjs check release-notes/1.3.5.md
 *
 * Exits 1 and says what is missing when the German part or the English part (under "## English") is empty or absent.
 */
import { readFileSync } from "node:fs";
import { checkNotes } from "./release-lib.mjs";

const [command, file] = process.argv.slice(2);
if (command !== "check" || !file) {
  console.error("Aufruf: node tools/release-notes.mjs check <Datei>");
  process.exit(2);
}
const problems = checkNotes(readFileSync(file, "utf8"));
for (const p of problems) console.error(`${file}: ${p}`);
process.exit(problems.length ? 1 : 0);
