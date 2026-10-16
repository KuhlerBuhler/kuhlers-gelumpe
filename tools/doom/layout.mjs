// SPDX-License-Identifier: AGPL-3.0-or-later
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { checkRam, checkRamPlacement } from "../../src/ramspans.mjs";
import { selectFor } from "../../src/patch.mjs";
import { FREE_RUNS } from "../../data/patch-ram.mjs";
import protectedMap from "../../data/protected.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
export const DOOM_LAYOUT = JSON.parse(readFileSync(new URL("layout.json", import.meta.url), "utf8"));

export function currentPatches(setPath = "data/patches/blech.json", extraPaths = []) {
  const set = JSON.parse(readFileSync(resolve(root, setPath), "utf8"));
  if (set.format !== "gelumpe-patch-set" || set.version !== 1 || !Array.isArray(set.patches)) {
    throw new Error("Ungültiger BLECH-Patchsatz");
  }
  const patches = [...set.patches, ...extraPaths].map(path => JSON.parse(readFileSync(resolve(root, path), "utf8")));
  const selected = selectFor(patches, "hacktribe");
  if (selected.reasons.length) throw new Error(selected.reasons.join("\n"));
  // The loader is a patch of the set itself now; the build here adds it to the base, so the base is the set without it.
  return selected.patches.filter(patch => patch.id !== "doom-loader");
}

export function checkDoomLayout(patches, layout = DOOM_LAYOUT) {
  const doom = {
    id: "doom-start",
    changes: [{ file: layout.site - 0xc0000000 + 0x100, bytes: "00000000" }],
    ram: [
      { at: `0x${layout.bootstrap.toString(16)}`, length: layout.codeEnd - layout.bootstrap,
        what: "Doom SD loader code", source: "tools/doom/bootstrap.ld:.text" },
      { at: `0x${layout.codeEnd.toString(16)}`, length: layout.bssEnd - layout.codeEnd,
        what: "Doom SD loader state", source: "tools/doom/bootstrap.ld:.bss" },
      { at: `0x${layout.shared.toString(16)}`, length: layout.end - layout.shared,
        what: "Doom runtime telemetry", source: "tools/doom/runtime_abi.h:DOOM_SHARED_ADDRESS" },
    ],
  };
  return [
    ...checkRam([...patches, doom]),
    ...checkRamPlacement([...patches, doom], {
      free: FREE_RUNS, regions: protectedMap.regions, window: protectedMap.ram.window,
      image: protectedMap.regions.find(region => region.id === "firmware-image"),
    }),
  ];
}
