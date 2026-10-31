#!/usr/bin/env node
/**
 * Makes data/known-releases.json (src/blech-update.mjs): per build, every region the BLECH patches of the given releases
 * write, as hashes. Run it at each release with the release's own tag added, so a file patched with that release
 * can be updated later. It reads the patch files from the git tags and needs the user's own unpatched files to
 * learn the hashes of the original bytes; those never go into the output.
 *
 *   node tools/known-releases.mjs --hacktribe H.VSB --stock RED.VSB --synth BLUE.VSB v1.3.4 v1.3.5 v1.3.6 v1.3.7 worktree
 *
 * `worktree` stands for the patch files as they are on disk now.
 */
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { addRelease, emptyKnown } from "../src/blech-update.mjs";
import { buildOf } from "../src/firmware.mjs";
import { USB_NAME_URLS } from "../src/patcher.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const args = process.argv.slice(2);
const takeFlag = name => { const i = args.indexOf(name); return i < 0 ? null : args.splice(i, 2)[1]; };
const bases = { hacktribe: takeFlag("--hacktribe"), stock: takeFlag("--stock"), synth: takeFlag("--synth") };
const out = takeFlag("--out") ?? `${root}data/known-releases.json`;
const refs = args;
if (!refs.length || !Object.values(bases).every(Boolean)) {
  process.stderr.write("usage: known-releases.mjs --hacktribe F --stock F --synth F [--out F] <tag|worktree>...\n");
  process.exit(2);
}

const show = (ref, path) => {
  try {
    const text = ref === "worktree" ? readFileSync(root + path, "utf8") : execFileSync("git", ["-C", root, "show", `${ref}:${path}`], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    return JSON.parse(text);
  } catch { return null; }
};
const setOf = (ref, setPath) => {
  const set = show(ref, setPath);
  return set ? set.patches.map(p => show(ref, p)).filter(Boolean) : null;
};

const known = emptyKnown();
for (const ref of refs) {
  const release = ref === "worktree" ? "develop" : ref.replace(/^v/, "");
  for (const [build, file] of Object.entries(bases)) {
    const base = new Uint8Array(readFileSync(file));
    if (buildOf(base) !== build) throw new Error(`${file} is not a ${build} file`);
    const patches = setOf(ref, build === "synth" ? "data/patches/blech-synth.json" : "data/patches/blech.json");
    if (!patches) throw new Error(`${ref}: no set`);
    await addRelease(known, release, build, base, patches);
    const names = USB_NAME_URLS.map(u => show(ref, u)).filter(Boolean);
    if (names.length) await addRelease(known, release, build, base, names);
  }
}
writeFileSync(out, JSON.stringify(known) + "\n");
process.stdout.write(`${out}: ${known.releases.join(", ")}; ${Object.entries(known.builds).map(([b, r]) => `${b} ${r.length} regions`).join(", ")}\n`);
