#!/usr/bin/env node
/**
 * Builds the optional patch lang-de for one runtime build (docs/firmware-sprache.md): ÄÖÜäöüß in fonts 0, 1 and 3,
 * the German BLECH texts from data/lang/de/blech.json, the German text table and German copies of the runtime's string
 * tables, and the header at LANG that tools/patch/lang_texts.py:lang_arm checks (table, count, key).
 * Like the runtime it is built, not committed: its addresses follow the runtime build.
 *
 *   node tools/lang/lang_patch.mjs [--build hacktribe|stock|synth] [--out FILE]
 */
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { asmInclude } from "../../src/script/arm-tables.mjs";
import { LANG, LANG_END, glyphChanges, readArt, readFacts } from "./glyphs.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const RAM = 0xC0000000;
const HEADER = 16;
const fileOf = ram => ram - RAM + 0x100;
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const ff = n => sha(new Uint8Array(n).fill(0xFF));

export const LANG_BUILDS = ["hacktribe", "stock", "synth"];

export function langPatchPath(build, dir = `${root}data/patches/`) {
  return `${dir}lang-de${build === "hacktribe" ? "" : `-${build}`}.json`;
}

/** The runtime's numbered labels, their key, its string addresses and tables (tools/patch/script_hooks.py:lang_manifest). */
export function runtimeTexts(build) {
  const venv = `${root}tools/emu/.venv/bin/python`;
  const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
  const code = "import json,sys; from tools.patch.script_hooks import build; print(json.dumps(build(sys.stdin.read(), build=sys.argv[1]).lang_manifest()))";
  const result = spawnSync(python, ["-c", code, build], { cwd: root, input: asmInclude(), encoding: "utf8", maxBuffer: 1 << 26 });
  if (result.error || result.status) throw new Error(result.error?.message ?? result.stderr);
  return JSON.parse(result.stdout);
}

/** The patch lang-de for `build` from the runtime's texts, the font facts and the German texts. */
export function langPatch(build, runtime = runtimeTexts(build), texts = JSON.parse(readFileSync(`${root}data/lang/de/blech.json`, "utf8")).texts) {
  const glyphs = glyphChanges(readFacts(build), readArt(), LANG + HEADER);
  const blob = [];
  let cursor = glyphs.end;
  const german = {};
  for (const label of runtime.labels) {
    if (runtime.tables[label]) continue;
    const text = texts[label]?.text;
    if (text === undefined) throw new Error(`${label} is numbered but has no German text`);
    german[label] = cursor;
    const bytes = Buffer.from(`${text}\0`, "latin1");
    blob.push(bytes);
    cursor += bytes.length;
  }
  cursor = Math.ceil(cursor / 4) * 4;
  const table = cursor;
  cursor += 4 * runtime.labels.length;
  const copies = {};
  for (const [label, names] of Object.entries(runtime.tables)) {
    copies[label] = cursor;
    cursor += 4 * names.length;
  }
  if (cursor > LANG_END) throw new Error(`lang-de ends at 0x${cursor.toString(16)}, past 0x${LANG_END.toString(16)}`);
  const address = name => german[name] ?? copies[name] ?? Number(runtime.strings[name]);
  const words = [...runtime.labels.map(address), ...Object.values(runtime.tables).flatMap(names => names.map(address))];
  if (words.some(w => !Number.isInteger(w))) throw new Error("a table names a string the runtime does not have");
  const tail = new Uint8Array(cursor - glyphs.end);
  let o = 0;
  for (const b of blob) { tail.set(b, o); o += b.length; }
  const view = new DataView(tail.buffer);
  words.forEach((w, i) => view.setUint32(table - glyphs.end + 4 * i, w, true));
  const header = new Uint8Array(HEADER);
  const hv = new DataView(header.buffer);
  hv.setUint32(0, table, true);
  hv.setUint32(4, runtime.labels.length, true);
  hv.setUint32(8, Number(runtime.key), true);
  const raw = (ram, bytes) => ({ file: fileOf(ram), bytes: Buffer.from(bytes).toString("hex"), expect: ff(bytes.length) });
  return {
    format: "gelumpe-patch", version: 1, id: "lang-de", name: "Menüs auf Deutsch", builds: [build],
    changes: [raw(LANG, header), ...glyphs.changes, raw(glyphs.end, tail)],
    startPhase: [...glyphs.startPhase, { file: fileOf(LANG), length: HEADER, why: "menu_arm_load reads the header of the text table at the start" }],
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const value = name => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined);
  const build = value("--build") ?? "hacktribe";
  const out = value("--out") ?? langPatchPath(build);
  const patch = langPatch(build);
  writeFileSync(out, `${JSON.stringify(patch, null, 1)}\n`);
  console.log(`wrote ${out}`);
}
