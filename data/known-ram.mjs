/**
 * What the RAM search (src/ramsearch.mjs, idea 11) treats as known.
 *
 * Known comes from three places and none of them repeats a number that lives elsewhere: the
 * device map (data/map/, down to the single field; a field with `source: "unknown"` stays
 * visible), the protected list (data/protected.mjs, the memory map of docs/speicherbereiche.md as
 * regions, classified in FROM_PROTECTED; a test fails for a region that is not), and the few
 * areas of the memory map in AREAS and PATTERN_SLOTS.
 *
 * `explained` says whether the content is understood, not just that the area is known. Only
 * explained bytes are hidden. A heap, a work buffer or the system data between the stacks are
 * areas whose purpose is known and whose bytes are not: they stay visible and only name where a
 * change happened. `group` lets a search bring a hidden kind back with `show`.
 */

export const GROUPS = {
  image: "Firmware-Abbild (Code und statische Daten)",
  system: "Stacks und Kernelblöcke",
  map: "Felder der Gerätekarte",
  patterns: "Pattern-Slots",
};

export const FROM_PROTECTED = {
  "firmware-image": { group: "image", explained: true },
  "sysex-hook": { group: "image", explained: true },
  "task-stacks": { group: "system", explained: true },
  "task-control-blocks": { group: "system", explained: true },
  heap: { explained: false },
  "boot-clear": { explained: false },
  "sample-info-cache": { explained: false },
  "work-buffer": { explained: false },
  "start-stack": { group: "system", explained: true },
  "irq-stack": { group: "system", explained: true },
};

/** Protected regions no RAM read may touch, so there is nothing to hide in them. */
export const NOT_READ = ["loader", "dsp-ports"];

export const AREAS = [
  { id: "ff-block", start: 0xc01a2100, end: 0xc01ffff0, group: "image", explained: true, what: "FF-Block im Abbild", evidence: "docs/speicherbereiche.md" },
  { id: "globals", start: 0xc08a2940, end: 0xc08b2940, explained: false, what: "Globals-Basis", evidence: "measure:2026-10-08/boot-pattern-speicher" },
];

/**
 * The 250 pattern slots. That a slot holds the layout of data/map/pattern.mjs is derived from the
 * PTST and PTED marks measured in them and from the initial pattern table, which is the same block.
 * It was not read back field by field in RAM.
 */
export const PATTERN_SLOTS = {
  start: 0xc08b2940, count: 250, stride: 0x4000, group: "patterns", block: "pattern",
  what: "Pattern", evidence: "derived:2026-10-08/boot-pattern-speicher",
};
