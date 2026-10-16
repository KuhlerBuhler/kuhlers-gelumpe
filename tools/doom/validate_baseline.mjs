// SPDX-License-Identifier: AGPL-3.0-or-later
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { sha256 } from "../../src/firmware.mjs";
import { applyPatches } from "../../src/patch.mjs";
import { DOOM_LAYOUT, checkDoomLayout, currentPatches } from "./layout.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));

export function assertCandidate(candidate, rebuilt) {
  if (candidate.length !== rebuilt.length || candidate.some((byte, index) => byte !== rebuilt[index])) {
    throw new Error("Firmware entspricht nicht dem vollständigen aktuellen BLECH-Patchsatz");
  }
}

export async function validateBaseline(original, candidate, setPath = "data/patches/blech.json", extraPaths = []) {
  if (await sha256(original) !== DOOM_LAYOUT.originalSha256) throw new Error("Unbekannte Originalfirmware");
  const patches = currentPatches(setPath, extraPaths);
  const reasons = checkDoomLayout(patches);
  if (reasons.length) throw new Error(reasons.join("\n"));
  const rebuilt = await applyPatches(original, patches);
  if (!rebuilt.ok) throw new Error(rebuilt.reasons.join("\n"));
  assertCandidate(candidate, rebuilt.bytes);
  return {
    original_sha256: DOOM_LAYOUT.originalSha256,
    candidate_sha256: await sha256(candidate),
    patch_set: setPath,
    patch_set_sha256: await sha256(readFileSync(resolve(root, setPath))),
    extra_patches: extraPaths,
    patches: await Promise.all(patches.map(async patch => ({
      id: patch.id, sha256: await sha256(new TextEncoder().encode(JSON.stringify(patch))),
    }))),
    spans: rebuilt.spans,
    layout: DOOM_LAYOUT,
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const original = new Uint8Array(readFileSync(process.argv[2]));
    const candidate = new Uint8Array(readFileSync(0));
    console.log(JSON.stringify(await validateBaseline(original, candidate, process.argv[3], process.argv.slice(4))));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
