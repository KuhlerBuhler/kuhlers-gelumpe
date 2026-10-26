#!/usr/bin/env node
/**
 * Build the files that go with a BLECH release from your own SYSTEM.VSB
 * (docs/patcher.md, "Patch-Datei"):
 *
 *   E2_VSB=SYSTEM.VSB [E2_STOCK_VSB=red/SYSTEM.VSB] [E2_BLUE_VSB=blue/SYSTEM.VSB] npm run build:blech-patch -- [--vsb SYSTEM.VSB]
 *       [--stock SYSTEM.VSB] [--synth SYSTEM.VSB] [--out dist-release] [--set data/patches/blech.json] [--synth-set data/patches/blech-synth.json] [--version 1.0.0]
 *
 *   BLECH.patch                 the whole set in our own format, for this editor and apply.mjs; takes
 *                               any Hacktribe 2.02 whose code and fixed data match (src/patchfile.mjs), the same with the
 *                               blue Electribe's head, with --stock also Korg's own 2.02 and with --synth the blue's own 2.02
 *   BLECH-for-<sha8>.bsdiff     bsdiff 4 from exactly this input to BLECH, for
 *                               `bspatch SYSTEM.VSB BLECH.VSB BLECH-for-<sha8>.bsdiff`; <sha8> is the start of the input's sha256.
 *                               One for every firmware the file takes.
 *
 * Build it from the SYSTEM.VSB of Hacktribe's package (OFFICIAL_SHA256) and Korg's own SYSTEM.VSB 2.02
 * (STOCK_SHA256): those are the files the bsdiffs fit, and what the public brings. Any other input is built, with a warning.
 * The version defaults to the one in package.json. Every file is checked by
 * applying it again to its input and comparing with the result of the set.
 * The output folder is gitignored by default (dist-release/): the files are
 * built from the VSBs, so they are only ever released, never committed. Needs
 * the `bzip2` program.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches, selectFor } from "../src/patch.mjs";
import { applyPatchFile, buildPatchFile } from "../src/patchfile.mjs";
import { buildOf, sha256 } from "../src/firmware.mjs";
import { STOCK_SHA256, SYNTH_SHA256, HACKTRIBE_SHA256 as OFFICIAL_SHA256, withHead } from "../src/patcher.mjs";
import { applyBsdiff, buildBsdiff, copyMatches, parseBsdiff } from "./patch/bsdiff.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(name);
  return i < 0 ? fallback : args[i + 1];
};
const fail = message => {
  console.error(message);
  process.exit(1);
};

const vsbPath = option("--vsb", process.env.E2_VSB);
const stockPath = option("--stock", process.env.E2_STOCK_VSB);
const synthPath = option("--synth", process.env.E2_BLUE_VSB);
if (!vsbPath) fail("usage: build-blech-patch.mjs --vsb SYSTEM.VSB [--stock SYSTEM.VSB] [--out dist-release] [--set data/patches/blech.json] [--version 1.0.0]");
const outDir = resolve(root, option("--out", "dist-release"));
const setPath = resolve(root, option("--set", "data/patches/blech.json"));
const synthSetPath = resolve(root, option("--synth-set", "data/patches/blech-synth.json"));
const version = option("--version", JSON.parse(readFileSync(resolve(root, "package.json"), "utf8")).version);

const read = path => JSON.parse(readFileSync(path, "utf8"));
const set = read(setPath);
if (set.format !== "gelumpe-patch-set" || set.version !== 1 || !Array.isArray(set.patches)) fail(`${setPath}: not a gelumpe-patch-set 1`);
const patches = set.patches.map(p => read(resolve(root, p)));
const load = path => new Uint8Array(readFileSync(path));
const vsb = load(vsbPath);
const stock = stockPath ? load(stockPath) : undefined;
const synth = synthPath ? load(synthPath) : undefined;
const synthSet = synth && read(synthSetPath);
const synthPatches = synthSet && synthSet.patches.map(p => read(resolve(root, p)));
if (synth && buildOf(synth) !== "synth") fail(`${synthPath} is not the blue Electribe's own 2.02.`);
if (buildOf(vsb) !== "hacktribe") fail(`${vsbPath} is Korg's own 2.02; give it as --stock and Hacktribe's file as --vsb.`);
if (stock && buildOf(stock) !== "stock") fail(`${stockPath} is not Korg's own 2.02.`);

const applied = await applyPatches(vsb, patches);
if (!applied.ok) fail(`the set does not apply to ${vsbPath}:\n${applied.reasons.map(r => `  ${r}`).join("\n")}`);
const appliedStock = stock && await applyPatches(stock, patches);
if (appliedStock && !appliedStock.ok) fail(`the set does not apply to ${stockPath}:\n${appliedStock.reasons.map(r => `  ${r}`).join("\n")}`);
const appliedSynth = synth && await applyPatches(synth, synthPatches);
if (appliedSynth && !appliedSynth.ok) fail(`the synth set does not apply to ${synthPath}:\n${appliedSynth.reasons.map(r => `  ${r}`).join("\n")}`);
// Hacktribe with the blue head (Hacktribe's -e): the same set, only the two head bytes differ
const blue = withHead(vsb, "blue");
const appliedBlue = await applyPatches(blue, patches);
if (!appliedBlue.ok) fail(`the set does not apply to Hacktribe with the blue head:\n${appliedBlue.reasons.join("\n")}`);

const inputHash = await sha256(vsb);
if (inputHash !== OFFICIAL_SHA256) console.warn(`Warning: ${vsbPath} is not the SYSTEM.VSB of Hacktribe's package (sha256 ${OFFICIAL_SHA256}); the bsdiff will fit only this file.`);
const stockHash = stock && await sha256(stock);
if (stock && stockHash !== STOCK_SHA256) console.warn(`Warning: ${stockPath} is not Korg's SYSTEM.VSB 2.02 (sha256 ${STOCK_SHA256}); its bsdiff will fit only this file.`);
const synthHash = synth && await sha256(synth);
if (synth && synthHash !== SYNTH_SHA256) console.warn(`Warning: ${synthPath} is not Korg's blue SYSTEM.VSB 2.02 (sha256 ${SYNTH_SHA256}); its bsdiff will fit only this file.`);

// [input, applied, patches, build, label] of every firmware the file takes
const inputs = [
  [vsb, applied, patches, "hacktribe", "Hacktribe 2.02"],
  [blue, appliedBlue, patches, "hacktribe", "Hacktribe 2.02 with the blue head"],
  ...(stock ? [[stock, appliedStock, patches, "stock", "Korg's own 2.02"]] : []),
  ...(synth ? [[synth, appliedSynth, synthPatches, "synth", "the blue's own 2.02"]] : []),
];
const patchFile = await buildPatchFile(vsb, patches, { version, id: set.id, name: set.name, stock, synth, synthPatches });
for (const [input, output, , , label] of inputs) {
  const again = await applyPatchFile(input, patchFile);
  if (!again.ok || again.bytes.some((b, i) => b !== output.bytes[i])) fail(`BLECH.patch does not give the same image as the set for ${label}`);
}

mkdirSync(outDir, { recursive: true });
writeFileSync(resolve(outDir, "BLECH.patch"), patchFile);
console.log(`${outDir}/BLECH.patch   ${patchFile.length} bytes`);

// The bsdiff for Hacktribe with the blue head gives the copy with the Sampler head: whoever has that file runs Hacktribe on
// the blue, whose updater takes only the Sampler head (docs/messungen/2026-10-26-blech-hacktribe-blau.md), as the page does
for (const [input, given, list, build, label] of inputs) {
  const output = input === blue ? applied : given;
  const hash = await sha256(input);
  const bsdiff = buildBsdiff(input, output.bytes, copyMatches(selectFor(list, build).patches, output.spans));
  const viaBsdiff = applyBsdiff(input, bsdiff);
  if (viaBsdiff.length !== output.bytes.length || viaBsdiff.some((b, i) => b !== output.bytes[i])) fail(`the bsdiff for ${label} does not give the same image as the set`);
  const blocks = parseBsdiff(bsdiff);
  const name = `BLECH-for-${hash.slice(0, 8)}.bsdiff`;
  writeFileSync(resolve(outDir, name), bsdiff);
  console.log(`${set.name} ${version} on ${label}: input sha256 ${hash}`);
  console.log(`                output sha256 ${await sha256(output.bytes)}`);
  console.log(`${outDir}/${name}  ${bsdiff.length} bytes (extra block ${blocks.extra.length} bytes, diff block ${blocks.diff.length} bytes, ${blocks.diff.some(b => b) ? "NOT all zero" : "all zero"})`);
}
