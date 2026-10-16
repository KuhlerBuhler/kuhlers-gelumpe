/**
 * Is this the firmware the map was measured on, and is it still original?
 *
 * Two builds of Sampler 2.02 exist: Korg's own ("stock") and Hacktribe's. The map was measured on
 * Hacktribe's. `identify` says which one a file is (`build`) and recognises only Hacktribe's as the
 * measured one; for Korg's own it says what it lacks instead of failing at some later place.
 *
 * Size first, then a handful of things that must sit at their measured
 * places, then the factory slots against the release fingerprints. A file
 * this editor changed before still passes as "known", but no longer as
 * "original": its menus are longer and some slots differ, and the page says
 * so instead of offering it as the way back.
 */
import { checkInstruction } from "./guards.mjs";
import { BLOCKS, field, readRaw, offsetOf, TABLES } from "./map/index.mjs";
import { tableEntry } from "./map/address.mjs";
import ORIGINALS from "../data/originals.mjs";
import { FACTORY_SLOTS } from "./profile.mjs";
import { locateModTable } from "./modtable.mjs";

const text = (bytes, at, n) => String.fromCharCode(...bytes.subarray(at, at + n));

/**
 * Hacktribe adds code in a run of the image that Korg's build leaves erased (0xFF). Edits of presets, menus or the
 * start image never touch it, so it tells the two builds apart for every Hacktribe file, original or edited.
 * The same rule is tools/emu/firmware.py `build_of`. File offsets, the header is 0x100 bytes.
 */
const HACKTRIBE_CODE = { file: 0x170100, length: 0x40 };

/** The head of the blue Electribe 2 (synth) ends its file type in "E2", the Sampler's in "E2S": derived from one file of
 * each (docs/messungen/2026-10-15-blaue-electribe.md). The service identifies by code (tools/emu/firmware.py). */
const isSynth = bytes => bytes.length > 0x12 && bytes[0x10] === 0x45 && bytes[0x11] === 0x32 && bytes[0x12] === 0;

/** @returns {"hacktribe" | "stock" | "synth"} */
export function buildOf(bytes) {
  if (isSynth(bytes)) return "synth";
  const run = bytes.subarray(HACKTRIBE_CODE.file, HACKTRIBE_CODE.file + HACKTRIBE_CODE.length);
  return run.length === HACKTRIBE_CODE.length && run.every(b => b === 0xff) ? "stock" : "hacktribe";
}

/**
 * What each build has. Hacktribe adds the SysEx commands 0x52 to 0x57 (live reading and writing of the RAM,
 * effect presets) and the preset tables the map describes. Korg's own build has none of them,
 * but it takes the BLECH patches (docs/messungen/2026-10-14-stock-blech.md; the rest measure:2026-10-14/stock-emulator).
 */
export const FEATURES = {
  hacktribe: { sysex: true, presets: true, patches: true },
  stock: { sysex: false, presets: false, patches: true },
  synth: { sysex: false, presets: false, patches: true },
};

/** The two hooks of BLECH's SysEx commands (tools/patch/blech_sysex.py): a branch into the patch's code, which lies in 0xC0172100 to 0xC0173800. */
const BLECH_SYSEX_HOOKS = [0xc0026a8c, 0xc0026418];

/** Whether a VSB carries BLECH's own SysEx commands: both hooks are branches into the patch's code. */
export function hasBlechSysex(bytes) {
  if (bytes.length < 0x200100) return false;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
  return BLECH_SYSEX_HOOKS.every(site => {
    const word = view.getUint32(site - 0xc0000000 + 0x100, true);
    if (word >>> 24 !== 0xea) return false;
    const target = site + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    return target >= 0xc0172100 && target < 0xc0173800;
  });
}

/** The one line for the blue Electribe 2: the emulator runs it, everything of the Sampler editor is not for it. */
export const SYNTH_REASON = "Das ist die Firmware der blauen Electribe 2 (Synth). Sie läuft im Emulator und hat einen eigenen BLECH-Patch-Satz. Der Effekt-Editor und die Live-Bearbeitung sind für den Sampler.";

/** The German lines for the page: what Korg's own build does not have. */
export const STOCK_LACKS = [
  "Lesen und Schreiben im RAM über MIDI und der Effekt-Editor (Hacktribe-SysEx, Befehle 0x52 bis 0x57)",
  "Effekt-Presets an den Stellen der Karte (Korgs Build legt sie verstreut ab, über zwei Zeigerfelder: der Editor liest sie darüber, aber nur aus der Datei, nicht live)",
  "BLECH und die Plugins, solange die Datei nicht gepatcht ist (der Patcher setzt BLECH direkt auf Korgs Build)",
  "Hacktribes Filter für den Synth und die zusätzlichen Effekte",
];

export const STOCK_REASON = `Das ist Korgs Original-Firmware 2.02. Es fehlt: ${STOCK_LACKS.join("; ")}.`;

/** Why a function of Hacktribe's is not offered for this build, or null when the build has it. */
export function lackOf(build, what = "sysex", { blech = false } = {}) {
  if (build === "stock" && what === "sysex" && blech) return null;
  if (build === "stock") return STOCK_REASON;
  if (build === "synth") return FEATURES.synth[what] ? null : SYNTH_REASON;
  return FEATURES[build]?.[what] ? null : "Die Firmware ist nicht erkannt.";
}

/**
 * Whether a file is a base the patches can be built on, and which build it is. Korg's own has none of the tables
 * `identify` looks for; the bytes each patch replaces are its real test (patch.mjs).
 * @returns {Promise<{ok: boolean, build: "hacktribe"|"stock"|null, reasons: string[]}>}
 */
export async function identifyBase(bytes) {
  const size = BLOCKS.get("firmware").size;
  if (bytes.length !== size) return { ok: false, build: null, reasons: [`Die Datei ist ${bytes.length} Byte groß; eine SYSTEM.VSB für 2.02 hat ${size}.`] };
  // The synth is a base for the patches made for it (builds: ["synth"]); each patch still checks the bytes it replaces.
  if (buildOf(bytes) === "synth") return { ok: true, build: "synth", reasons: [] };
  if (buildOf(bytes) === "hacktribe") {
    const id = await identify(bytes);
    return { ok: id.known, build: "hacktribe", reasons: id.reasons };
  }
  const init = tableEntry("table.initPattern", 0).file + offsetOf(field("pattern.magic"));
  return text(bytes, init, 4) === "PTST"
    ? { ok: true, build: "stock", reasons: [] }
    : { ok: false, build: "stock", reasons: ["Das Init-Pattern liegt nicht an der gemessenen Stelle."] };
}

export async function sha256(bytes) {
  const digest = new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", bytes));
  return [...digest].map(b => b.toString(16).padStart(2, "0")).join("");
}

export async function slotHash(bytes) {
  return (await sha256(bytes)).slice(0, 16);
}

const recordAt = (bytes, kind, slot) => {
  const { file, size } = tableEntry(`table.${kind}`, slot - 1);
  return bytes.subarray(file, file + size);
};

/**
 * @returns {Promise<{known: boolean, build: "hacktribe"|"stock"|null, reasons: string[], release: string|null,
 *   original: boolean, changedSlots: {mfx: number[], ifx: number[]},
 *   menus: {mfx: number, ifx: number, ifxAgreed: boolean}}>}
 */
export async function identify(bytes) {
  const reasons = [];
  const size = BLOCKS.get("firmware").size;
  if (bytes.length !== size) {
    return { known: false, build: null, reasons: [`Die Datei ist ${bytes.length} Byte groß; eine SYSTEM.VSB für 2.02 hat ${size}.`], release: null, original: false, changedSlots: null, menus: null };
  }
  const build = buildOf(bytes);
  if (build === "synth") return { known: false, build, reasons: [SYNTH_REASON], release: null, original: false, changedSlots: null, menus: null };
  const init = tableEntry("table.initPattern", 0).file + offsetOf(field("pattern.magic"));
  if (text(bytes, init, 4) !== "PTST") reasons.push("Das Init-Pattern liegt nicht an der gemessenen Stelle.");
  // Korg's own build is a Sampler 2.02 image as well, but the tables the map describes are not in it.
  if (build === "stock" && !reasons.length) return { known: false, build, reasons: [STOCK_REASON], release: null, original: false, changedSlots: null, menus: null };
  const groove = tableEntry("table.groove", 0).file;
  if (text(bytes, groove + offsetOf(field("groove.magic")), 4) !== "GVST") reasons.push("Die Groove-Tabelle liegt nicht an der gemessenen Stelle.");
  const mod = locateModTable(bytes);
  if (!mod.ok) reasons.push(...mod.reasons);
  const ifx = readRaw(bytes, field("menu.ifxCount"));
  if (!ifx.agreed) reasons.push(`Die 13 Stellen der Insert-Menülänge sind sich nicht einig (${ifx.values.join(", ")}).`);
  const mfx = readRaw(bytes, field("menu.mfxCount"));
  const ins = field("menu.mfxCount");
  try { checkInstruction(bytes.subarray(ins.where.offset, ins.where.offset + 4), ins.instruction, ins.id); }
  catch (error) { reasons.push(error.message); }
  const tables = ["mfx", "ifx"].map(k => TABLES.get(`table.${k}`));
  if (mfx < FACTORY_SLOTS.mfx || mfx > tables[0].count) reasons.push(`Die Master-Menülänge ${mfx} ist unplausibel.`);

  const menus = { mfx, ifx: ifx.value, ifxAgreed: ifx.agreed };
  if (reasons.length) return { known: false, build, reasons, release: null, original: false, changedSlots: null, menus };

  let best = null;
  for (const release of ORIGINALS) {
    const changed = { mfx: [], ifx: [] };
    for (const kind of ["mfx", "ifx"]) {
      for (let slot = 1; slot <= release[kind].length; slot++) {
        if (await slotHash(recordAt(bytes, kind, slot)) !== release[kind][slot - 1]) changed[kind].push(slot);
      }
    }
    const score = changed.mfx.length + changed.ifx.length;
    if (!best || score < best.score) best = { release: release.release, changed, score, slots: release };
  }
  const original = best.score === 0 && menus.mfx === best.slots.mfx.length && menus.ifx === best.slots.ifx.length;
  return { known: true, build, reasons, release: best.release, original, changedSlots: best.changed, menus };
}

/** Whether one factory slot is byte for byte the release, for the baseline rule. */
export async function isOriginalSlot(record, kind, slot) {
  for (const release of ORIGINALS) {
    const list = release[kind];
    if (slot >= 1 && slot <= list.length && await slotHash(record) === list[slot - 1]) return true;
  }
  return false;
}
