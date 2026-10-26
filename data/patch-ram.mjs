/**
 * The runs of the firmware image where a patch may keep RAM of its own (`ram`, src/ramspans.mjs).
 * The image is protected as a whole (data/protected.mjs, `firmware-image`), so an area in it is only
 * free where the image is erased (FF), measured at the Hacktribe build. A declared area must lie
 * wholly in one run. Intervals are half open.
 */
import { AREAS } from "./known-ram.mjs";

const largest = AREAS.find(a => a.id === "ff-block");

export const FREE_RUNS = [
  {
    start: 0xc01720b0, end: 0xc01a0000,
    what: "FF im Abbild vor dem Hacktribe-Code ab 0xC01A0000",
    evidence: "docs/hintergrund/startbild-editor.md, Abschnitt Platz",
  },
  {
    start: largest.start, end: largest.end,
    what: "größter FF-Block im Abbild",
    evidence: "docs/speicherbereiche.md, docs/patcher.md Speicherorte",
  },
];

/**
 * RAM behind the firmware image where a patch may keep buffers of its own. Every measured phase left it untouched: the
 * device while playing, the emulator over start, play, pattern switch, DATA UTILITY import and export and power off.
 */
export const HIGH_RUNS = [{
  start: 0xc274f000, end: 0xc4000000,
  what: "RAM über dem Interrupt-Stack bis zum Ende der 64 MiB",
  evidence: "docs/messungen/2026-10-22-ram-frei.md, docs/messungen/2026-10-25-sample-swap-timeout.md",
}];

export const SYNTH_FREE_RUNS = [{
  start: 0xc01217f4, end: 0xc01ffff0,
  what: "FF-Block im blauen Original 2.02",
  evidence: "docs/messungen/2026-10-16-blech-synth.md",
}];

/**
 * RAM no patch of the set may use because something outside the set lives there. Empty since Doom's SD loader became a
 * patch of the set (data/patches/doom-loader.json, RAM 0xC017CC00 to 0xC0180000), whose own `ram` list the set's overlap check
 * already holds against every other patch. Add an entry here only for something that is not a patch.
 */
export const RESERVED = [];
