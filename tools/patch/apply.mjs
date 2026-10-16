#!/usr/bin/env node
/**
 * Apply patches to a copy of your own SYSTEM.VSB (docs/patcher.md).
 *
 *   node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch data/patches/splash-editor.json --out NEW.VSB
 *   node tools/patch/apply.mjs --vsb SYSTEM.VSB --set data/patches/blech.json --out NEW.VSB
 *   node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch BLECH.patch --out NEW.VSB
 *
 * A set (format gelumpe-patch-set) lists patch files relative to the repository root.
 * A patch file (src/patchfile.mjs, built by tools/build-blech-patch.mjs) is a whole set in one
 * file and is given alone; it also checks the VSB and the result against the hashes in its header.
 *
 * Writes only the new file and prints the emulator check to run on it. The
 * input is never touched, no patch carries firmware bytes, and nothing here
 * flashes anything.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { applyPatches } from "../../src/patch.mjs";
import { applyPatchFile, isPatchFile } from "../../src/patchfile.mjs";
import { sha256 } from "../../src/firmware.mjs";

const args = process.argv.slice(2);
const take = name => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []));
const [vsbPath] = take("--vsb");
const [outPath] = take("--out");
const root = fileURLToPath(new URL("../../", import.meta.url));
const [patchFile] = take("--patch").filter(p => isPatchFile(readFileSync(p)));
const patchPaths = [
  ...take("--set").flatMap(path => {
    const set = JSON.parse(readFileSync(path, "utf8"));
    if (set.format !== "gelumpe-patch-set" || set.version !== 1 || !Array.isArray(set.patches)) {
      process.stderr.write(`${path}: not a gelumpe-patch-set 1\n`);
      process.exit(2);
    }
    return set.patches.map(p => `${root}${p}`);
  }),
  ...take("--patch").filter(p => p !== patchFile),
];
if (!vsbPath || !outPath || !(patchPaths.length || patchFile)) {
  process.stderr.write("usage: apply.mjs --vsb SYSTEM.VSB (--patch patch.json [--patch more.json] | --set set.json | --patch BLECH.patch) --out NEW.VSB\n");
  process.exit(2);
}
if (patchFile && (patchPaths.length || take("--patch").length > 1)) {
  process.stderr.write("a patch file is a whole set: give it alone\n");
  process.exit(2);
}

const vsb = new Uint8Array(readFileSync(vsbPath));
const result = patchFile
  ? await applyPatchFile(vsb, new Uint8Array(readFileSync(patchFile)))
  : await applyPatches(vsb, patchPaths.map(p => JSON.parse(readFileSync(p, "utf8"))));
if (!result.ok) {
  process.stderr.write(`not applied:\n${result.reasons.map(r => `  ${r}`).join("\n")}\n`);
  process.exit(1);
}
writeFileSync(outPath, result.bytes);
const hex = n => `0x${n.toString(16)}`;
console.log(`wrote ${outPath} (${result.bytes.length} bytes), sha256 ${await sha256(result.bytes)}`);
if (result.file) console.log(`  ${result.file.name} ${result.file.version}: input and output match the patch file`);
for (const s of result.spans) console.log(`  ${s.patch}: ${hex(s.file)} + ${s.length}`);
const allow = [...result.allow.map(([at, n]) => ["--allow", at, n]), ...result.allowCode.map(([at, n]) => ["--allow-code", at, n])];
console.log("\nrun before flashing (the span lists are what the patches say runs at start):");
console.log(`  tools/emu/.venv/bin/python tools/emu/check.py --base ${vsbPath} --patched ${outPath} ${allow.map(([f, at, n]) => `${f} ${hex(at)}:${n}`).join(" ")} [--flash dump.bin]`);
