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
import { render, text as textOf } from "./text.mjs";

/** A reason as finished text in the current language (src/text.mjs): reasons are lists of strings everywhere they go. */
const say = (key, vars) => render(textOf(key, vars));

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

/** The Electribe a file is made for, by its head: Hacktribe for the blue carries the blue head (tools/emu/firmware.py, hardware_of_head). */
export const hardwareOf = bytes => (isSynth(bytes) ? "blue" : "red");

/** CRC-32 of the run in Hacktribe 2.02 (`7cb4825c`); the same in every Hacktribe file, BLECH never writes there. */
const HACKTRIBE_RUN_CRC = 0x12224d92;

function crc32(bytes) {
  let crc = ~0;
  for (const b of bytes) {
    crc ^= b;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return ~crc >>> 0;
}

/** @returns {"hacktribe" | "stock" | "synth"} */
export function buildOf(bytes) {
  const run = bytes.subarray(HACKTRIBE_CODE.file, HACKTRIBE_CODE.file + HACKTRIBE_CODE.length);
  const erased = run.length === HACKTRIBE_CODE.length && run.every(b => b === 0xff);
  // With the synth head only Hacktribe's own run makes it Hacktribe for the blue (docs/ideen/65-blech-hacktribe-blau.md); any
  // other blue file stays the blue's, so an altered one hears "take Korg's original", not a Hacktribe fingerprint
  if (isSynth(bytes)) return !erased && crc32(run) === HACKTRIBE_RUN_CRC ? "hacktribe" : "synth";
  return erased ? "stock" : "hacktribe";
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
/** The same hooks in the blue Electribe 2's firmware (data/patches/blech-sysex-synth.json). */
const BLECH_SYSEX_HOOKS_SYNTH = [0xc002240c, 0xc0021d70];

/** Whether a VSB carries BLECH's own SysEx commands: both hooks are branches into the patch's code. */
export function hasBlechSysex(bytes, hooks = BLECH_SYSEX_HOOKS) {
  if (bytes.length < 0x200100) return false;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
  return hooks.every(site => {
    const word = view.getUint32(site - 0xc0000000 + 0x100, true);
    if (word >>> 24 !== 0xea) return false;
    const target = site + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
    return target >= 0xc0172100 && target < 0xc0173800;
  });
}

/**
 * What a VSB is, in the words the emulator's display shows: Korg's firmware of the red or the blue Electribe, Hacktribe on
 * either (Hacktribe's code on a blue one keeps the blue head), each with BLECH or without.
 */
export function firmwareName(bytes) {
  const synthHead = isSynth(bytes);
  const run = bytes.subarray(HACKTRIBE_CODE.file, HACKTRIBE_CODE.file + HACKTRIBE_CODE.length);
  const hacktribe = run.length === HACKTRIBE_CODE.length && !run.every(b => b === 0xff);
  const blech = hasBlechSysex(bytes) || (synthHead && !hacktribe && hasBlechSysex(bytes, BLECH_SYSEX_HOOKS_SYNTH));
  const device = synthHead ? "Synth" : "Sampler";
  if (hacktribe) return `${blech ? "Bleched Hacktribe" : "Hacktribe"} ${device}`;
  return blech ? `Blechtribe ${device}` : device;
}

/** The one line for the blue Electribe 2: the emulator runs it, everything of the Sampler editor is not for it. */
const synthReason = () => say("vsb.synth");

/** The lines for the page, as texts: what Korg's own build does not have. */
export const STOCK_LACKS = [textOf("vsb.lack.sysex"), textOf("vsb.lack.presets"), textOf("vsb.lack.blech"), textOf("vsb.lack.filters")];

const stockReason = () => say("vsb.stock", { lacks: STOCK_LACKS.map(render).join("; ") });

/** The two reasons as Node renders them, German: for tests and tools. The page gets them through lackOf() and identify(). */
export const SYNTH_REASON = synthReason();
export const STOCK_REASON = stockReason();

/** Why a function of Hacktribe's is not offered for this build, or null when the build has it. */
export function lackOf(build, what = "sysex", { blech = false } = {}) {
  if (build === "stock" && what === "sysex" && blech) return null;
  if (build === "stock") return stockReason();
  if (build === "synth") return FEATURES.synth[what] ? null : synthReason();
  return FEATURES[build]?.[what] ? null : say("vsb.unknown");
}

/**
 * Whether a file is a base the patches can be built on, and which build it is. Korg's own has none of the tables
 * `identify` looks for; the bytes each patch replaces are its real test (patch.mjs).
 * @returns {Promise<{ok: boolean, build: "hacktribe"|"stock"|null, reasons: string[]}>}
 */
export async function identifyBase(bytes) {
  const size = BLOCKS.get("firmware").size;
  if (bytes.length !== size) return { ok: false, build: null, reasons: [say("vsb.size", { got: bytes.length, size })] };
  // The synth is a base for the patches made for it (builds: ["synth"]); each patch still checks the bytes it replaces.
  if (buildOf(bytes) === "synth") return { ok: true, build: "synth", reasons: [] };
  if (buildOf(bytes) === "hacktribe") {
    const id = await identify(bytes);
    return { ok: id.known, build: "hacktribe", reasons: id.reasons };
  }
  const init = tableEntry("table.initPattern", 0).file + offsetOf(field("pattern.magic"));
  return text(bytes, init, 4) === "PTST"
    ? { ok: true, build: "stock", reasons: [] }
    : { ok: false, build: "stock", reasons: [say("vsb.initPattern")] };
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
    return { known: false, build: null, reasons: [say("vsb.size", { got: bytes.length, size })], release: null, original: false, changedSlots: null, menus: null };
  }
  const build = buildOf(bytes);
  if (build === "synth") return { known: false, build, reasons: [synthReason()], release: null, original: false, changedSlots: null, menus: null };
  const init = tableEntry("table.initPattern", 0).file + offsetOf(field("pattern.magic"));
  if (text(bytes, init, 4) !== "PTST") reasons.push(say("vsb.initPattern"));
  // Korg's own build is a Sampler 2.02 image as well, but the tables the map describes are not in it.
  if (build === "stock" && !reasons.length) return { known: false, build, reasons: [stockReason()], release: null, original: false, changedSlots: null, menus: null };
  const groove = tableEntry("table.groove", 0).file;
  if (text(bytes, groove + offsetOf(field("groove.magic")), 4) !== "GVST") reasons.push(say("vsb.groove"));
  const mod = locateModTable(bytes);
  if (!mod.ok) reasons.push(...mod.reasons);
  const ifx = readRaw(bytes, field("menu.ifxCount"));
  if (!ifx.agreed) reasons.push(say("vsb.ifxMenu", { values: ifx.values.join(", ") }));
  const mfx = readRaw(bytes, field("menu.mfxCount"));
  const ins = field("menu.mfxCount");
  try { checkInstruction(bytes.subarray(ins.where.offset, ins.where.offset + 4), ins.instruction, ins.id); }
  catch (error) { reasons.push(error.message); }
  const tables = ["mfx", "ifx"].map(k => TABLES.get(`table.${k}`));
  if (mfx < FACTORY_SLOTS.mfx || mfx > tables[0].count) reasons.push(say("vsb.mfxMenu", { mfx }));

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

/** What to tell a beginner when `identify` does not know the file: what it is and what to take instead; the reasons follow. */
export function firmwareAdvice(id, reasons = id.reasons) {
  if (!id.build) return say("vsb.advice.none");
  if (id.build === "synth") return say("vsb.advice.synth");
  if (id.build === "stock") return say("vsb.advice.stock");
  return say("vsb.advice.unknown", { reasons: reasons.join(" ") });
}

/** Whether one factory slot is byte for byte the release, for the baseline rule. */
export async function isOriginalSlot(record, kind, slot) {
  for (const release of ORIGINALS) {
    const list = release[kind];
    if (slot >= 1 && slot <= list.length && await slotHash(record) === list[slot - 1]) return true;
  }
  return false;
}
