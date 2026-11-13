#!/usr/bin/env node
/**
 * Writes the table "Coverage" of docs/plugins.md, plugins.en.md and plugins.fr.md from data/script/coverage.mjs, between the
 * lines `<!-- coverage -->` and `<!-- /coverage -->`. `--check` writes nothing and exits 1 when a doc differs.
 *
 *   node tools/plugin-coverage.mjs [--check]
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { AREAS, COVERAGE } from "../data/script/coverage.mjs";

export const DOCS = Object.freeze({ de: "docs/plugins.md", en: "docs/plugins.en.md", fr: "docs/plugins.fr.md" });
const HEAD = {
  de: ["Bereich", "Lesen", "Setzen", "Event", "nein"],
  en: ["Part", "Read", "Set", "Event", "no"],
  fr: ["Élément", "Lire", "Régler", "Événement", "non"],
};
export const START = "<!-- coverage -->";
export const END = "<!-- /coverage -->";

/** The table in one language, without the marker lines. */
export function coverageTable(lang) {
  const [part, read, set, event, none] = HEAD[lang];
  const cell = names => (names.length ? names.map(n => `\`${n}\``).join(", ") : none);
  const lines = [];
  for (const [area, label] of Object.entries(AREAS)) {
    lines.push(`| **${label[lang]}** | | | |`);
    for (const r of COVERAGE.filter(c => c.area === area)) lines.push(`| ${r.label[lang]} | ${cell(r.read)} | ${cell(r.write)} | ${cell(r.events)} |`);
  }
  return [`| ${part} | ${read} | ${set} | ${event} |`, "|---|---|---|---|", ...lines].join("\n");
}

/** The doc with the current table between its markers; throws when the markers are missing. */
export function withTable(doc, lang) {
  const a = doc.indexOf(START), b = doc.indexOf(END);
  if (a < 0 || b < a) throw new Error(`${DOCS[lang]}: no ${START} ... ${END}`);
  return `${doc.slice(0, a + START.length)}\n${coverageTable(lang)}\n${doc.slice(b)}`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const check = process.argv.includes("--check");
  let stale = false;
  for (const [lang, path] of Object.entries(DOCS)) {
    const file = fileURLToPath(new URL(`../${path}`, import.meta.url));
    const doc = readFileSync(file, "utf8"), next = withTable(doc, lang);
    if (doc === next) continue;
    stale = true;
    if (check) console.error(`${path}: the coverage table is not current, run node tools/plugin-coverage.mjs`);
    else { writeFileSync(file, next); console.log(`wrote ${path}`); }
  }
  process.exit(check && stale ? 1 : 0);
}
