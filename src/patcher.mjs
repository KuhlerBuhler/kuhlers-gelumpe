/** The Patcher page's logic without the page: what a dropped SYSTEM.VSB is, the BLECH patches, the state from drop to download. */
import { buildOf, hardwareOf, identifyBase, sha256 } from "./firmware.mjs";
import { applyPatches, buildsOf, patchesPresent, selectFor } from "./patch.mjs";
import { loadingAnimPatch, LOADING_ANIM_ID } from "./loading-anim.mjs";
import { applyBsdiff, parseBsdiff } from "./bsdiff.mjs";
import { text, isText, TextError, number } from "./text.mjs";

export const VSB_SIZE = 0x200100;
/** Korg's electribe sampler 2.02 SYSTEM.VSB, as in hacktribe/scripts/e2-firmware-patch.py and on the user's own copy. */
export const STOCK_SHA256 = "1d0f0689d5a12c8a8bde9f821f2a59adc5f6cd6012ddb201ebb192b72468a646";
export const SYNTH_SHA256 = "41fc5f1c33209ef381d1c9fef21a72380bcd8d3431c9c1350a964f5c619ab8b8";

/** Hacktribe 2.02 as hacktribe/scripts/e2-firmware-patch.py builds it: hash/hacked-SYSTEM.VSB.sha, and the same on the user's own copy. */
export const HACKTRIBE_SHA256 = "7cb4825c184a7e3fa92224304be22a788c96c4b748c277e63a496baa9faae7ee";
/** hacktribe-2.patch is not open source (README of bangcorrupt/hacktribe), so it is linked, never shipped or fetched by the page. */
export const HACKTRIBE_PATCH_URL = "https://github.com/bangcorrupt/hacktribe/raw/main/patch/hacktribe-2.patch";
/** The real file is 17.6 KB; anything near a megabyte is not it. */
export const HACKTRIBE_PATCH_MAX = 1 << 20;

/**
 * Hacktribe for the blue Electribe 2 is Hacktribe 2.02 with the blue head (Hacktribe's e2-firmware-patch.py -e): byte
 * 0x12 = 0x00, 0x2E = 0x23 (docs/ideen/65-blech-hacktribe-blau.md). Korg's blue firmware takes only that head; once
 * Hacktribe runs on the blue, its updater takes only the Sampler head (0x53, 0x24), and so do later BLECH updates.
 */
export const HACKTRIBE_BLUE_SHA256 = "2b2e1c2f928c1faf4cc2a6580292763a5282a37f19eb9165c1bdd05db832ddbe";
const HEADS = { sampler: [[0x12, 0x53], [0x2e, 0x24]], blue: [[0x12, 0x00], [0x2e, 0x23]] };

/** A copy of the file with the Sampler's or the blue's head. Only the two bytes change. */
export function withHead(bytes, head) {
  const out = Uint8Array.from(bytes);
  for (const [at, value] of HEADS[head]) out[at] = value;
  return out;
}
export const samplerHead = bytes => withHead(bytes, "sampler");

/**
 * Korg's System Updater 2.02 per Electribe: the support page with Korg's licence agreement, and the zip on Korg's download
 * server. The page offers the download only after the user accepted the agreement; the app fetches it natively
 * (src-tauri/src/korg.rs, the same URLs), the browser only links it, since Korg's server sends no CORS header.
 */
export const KORG_DOWNLOADS = {
  red: {
    page: "https://www.korg.com/us/support/download/software/0/368/2579/",
    file: "https://cdn.korg.com/us/support/download/files/0b87bcd3112fbb8c0ad7b0f55e618837.zip?response-content-disposition=attachment%3Bfilename%2A%3DUTF-8%27%27electribe_sampler_system_v202.zip&response-content-type=application%2Foctet-stream%3B",
  },
  blue: {
    page: "https://www.korg.com/us/support/download/software/0/367/2578/",
    file: "https://cdn.korg.com/us/support/download/files/89f5b5eb14071e3456ceedd534618d8a.zip?response-content-disposition=attachment%3Bfilename%2A%3DUTF-8%27%27electribe_system_v202.zip&response-content-type=application%2Foctet-stream%3B",
  },
};

/** Where the BLECH set lives, relative to the page: the one list of what BLECH is (docs/patcher.md). */
export const BLECH_SET_URL = "data/patches/blech.json";
export const BLECH_SYNTH_SET_URL = "data/patches/blech-synth.json";
/**
 * The optional patch "Gerätename: Electribe 3" (docs/ideen/69-geraetename.md), off unless the user picks it: one variant
 * for the red (Hacktribe and Korg's own) and one for the blue. Not part of a set, so a set alone never renames the device.
 */
export const USB_NAME_URLS = ["data/patches/usb-name.json", "data/patches/usb-name-synth.json"];

/**
 * A patched copy with the user's own loading animation on top, in a pass of its own: load-bar declares the slot as its
 * RAM, so in one list with load-bar the patch would collide with it. Written only when load-bar went on, since nothing
 * else reads the slot; no file (null) keeps the default Blechy. Throws on a file the firmware would reject.
 */
export async function withLoadingAnim(res, anim) {
  if (!res.ok || !anim || !res.spans.some(s => s.patch === "load-bar")) return res;
  const more = await applyPatches(res.bytes, [loadingAnimPatch(anim)]);
  if (!more.ok) return { ...more, dependencies: res.dependencies };
  return { ...more, dependencies: res.dependencies, spans: [...res.spans, ...more.spans], allow: [...res.allow, ...more.allow], allowCode: [...res.allowCode, ...more.allowCode] };
}

/** The variant of an optional patch (its variants parsed) for a firmware build, or null when none is made for it. */
export const optionFor = (variants, build) => variants.find(p => buildsOf(p).includes(build)) ?? null;
/** Copies that already passed the whole emulator check, as SHA-256 of input and result (tools/verify-patches.mjs). */
export const VERIFIED_URL = "data/patches/verified.json";

/**
 * The page's name for each patch it knows, a key of the app's tables, so the plan reads in the user's language; where
 * the variants of one id say different things, one per build. The JSON `name` stays the build's own label.
 */
const PATCH_LABELS = {
  "splash-editor": "features.splash.title",
  "mfx-switch": "features.mfx2.title",
  "pattern-switch": "features.patternSwitch.title",
  "tap-motion": "features.tapMotion.title",
  "note-assistant": "features.noteAssist.title",
  "dice": "features.dice.title",
  "pad-colors": "features.colors.title",
  "load-bar": "features.loading.title",
  [LOADING_ANIM_ID]: "patcher.patch.loadingAnim",
  "sample-errors": "features.sampleErrors.title",
  "script-runtime": "features.plugins.title",
  "splash": "patcher.patch.splash",
  "blech-theme": "features.theme.title",
  "preset-tables": "patcher.patch.presetTables",
  "fx-catalog": "patcher.patch.fxCatalog",
  "synth-filters": "patcher.patch.synthFilters",
  "power-off": "features.powerOff.title",
  "last-pattern": "features.lastPattern.title",
  "init-pattern": "features.initPattern.title",
  "stereo-pad": "features.stereoPad.title",
  "beat-eighth": "features.beatEighth.title",
  "blech-version": "patcher.patch.version",
  "doom-loader": "features.doom.title",
  "blech-sysex": { synth: "patcher.patch.sysexSynth", other: "patcher.patch.sysex" },
  "ifx-idle": "patcher.patch.ifxIdle",
  "usb-name": "patcher.usbName",
};

/** The label of a parsed patch for the page: a text of the tables, or the file's own name for a patch the page does not know. */
export function patchLabel(patch) {
  const build = buildsOf(patch ?? {})[0];
  if (patch?.id === "blechtribe") return text("patcher.patch.blechtribe", { folder: FOLDER[build] ?? "hacktribe" });
  const key = PATCH_LABELS[patch?.id];
  const pick = typeof key === "object" ? key[build] ?? key.other : key;
  return pick ? text(pick) : patch?.name ?? patch?.id;
}

/**
 * The BLECH set and its patches, read through `fetchJson(url)` (urls are relative to the page, as the set
 * lists them relative to the repository root). The set is the single source: the page applies exactly what
 * `apply.mjs --set data/patches/blech.json` applies. `items` are {id, label, url} for the page, `patches` the parsed files.
 */
export async function loadBlechSet(fetchJson, setUrl = BLECH_SET_URL) {
  const set = await fetchJson(setUrl);
  if (set?.format !== "gelumpe-patch-set" || set.version !== 1 || !Array.isArray(set.patches) || !set.patches.length) {
    throw new TextError("patcher.reason.noSet", { url: setUrl });
  }
  const patches = await Promise.all(set.patches.map(url => fetchJson(url)));
  const items = patches.map((p, i) => ({ id: p?.id, label: patchLabel(p), url: set.patches[i] }));
  return { id: set.id, name: set.name, items, patches };
}

/** The items of a loaded set (`loadBlechSet`) that apply to a firmware build: per id the variant made for it. */
export const itemsFor = (blech, build) => blech.items.filter((_, i) => buildsOf(blech.patches[i]).includes(build));

/**
 * kind: wrong-size, stock (Korg's unchanged 2.02), hacktribe, blech (every patch is in already), partial (some are),
 * unknown; `present` lists the patch ids found. An unknown file of Korg's build that is not Korg's unchanged file
 * carries `changed` ("stock" or "synth"): the original of that Electribe is the one to take instead. A file of Korg's build is only accepted as the unchanged original
 * or when it already carries the BLECH patches made for it.
 */
export async function classify(bytes, patches, stockHash = STOCK_SHA256, synthHash = SYNTH_SHA256) {
  const hash = await sha256(bytes);
  // sha256: what support needs to tell which file was dropped
  const out = { kind: "unknown", size: bytes.length, sha256: hash, reasons: [], present: [] };
  if (bytes.length !== VSB_SIZE) return { ...out, kind: "wrong-size" };
  if (hash === stockHash) return { ...out, kind: "stock" };
  if (hash === synthHash) return { ...out, kind: "synth" };
  const base = await identifyBase(bytes);
  if (!base.ok) return { ...out, reasons: base.reasons };
  const mine = selectFor(patches, base.build).patches;
  const present = (await patchesPresent(bytes, mine)).filter(p => p.present).map(p => p.id);
  if (base.build === "synth" && !present.length) {
    return { ...out, changed: "synth", reasons: [text("patcher.reason.synthChanged")] };
  }
  if (base.build === "stock" && !present.length) {
    return { ...out, changed: "stock", reasons: [text("patcher.reason.stockChanged", { sha: stockHash.slice(0, 8) })] };
  }
  const kind = present.length === 0 ? "hacktribe" : present.length === mine.length ? "blech" : "partial";
  // hardware: the head says which Electribe a Hacktribe file is for (the blue one carries the synth head)
  return { ...out, kind, present, hardware: hardwareOf(bytes) };
}

/**
 * Korg's 2.02 and the user's own hacktribe-2.patch (bsdiff4, BSDIFF40) make Hacktribe 2.02. Checks the file
 * before and the result after: {ok, bytes, sha256} or {ok: false, reason}. Hashes are parameters for tests.
 */
export async function convertStock(stock, patch, { stockHash = STOCK_SHA256, targetHash = HACKTRIBE_SHA256 } = {}) {
  if (await sha256(stock) !== stockHash) return { ok: false, reason: text("patcher.reason.notStock") };
  if (patch.length > HACKTRIBE_PATCH_MAX) return { ok: false, reason: text("patcher.reason.patchTooBig", { size: number(patch.length) }) };
  try {
    const { newSize } = parseBsdiff(patch);
    if (newSize !== VSB_SIZE) return { ok: false, reason: text("patcher.reason.patchSize", { size: number(newSize), expected: number(VSB_SIZE) }) };
    const bytes = applyBsdiff(stock, patch, { maxNewSize: VSB_SIZE });
    const hash = await sha256(bytes);
    if (hash !== targetHash) return { ok: false, reason: text("patcher.reason.notHacktribe") };
    return { ok: true, bytes, sha256: hash };
  } catch (e) {
    return { ok: false, reason: e.message };
  }
}

/** The files the patcher takes as an original: Korg's 2.02 of the red and the blue, Hacktribe's 2.02 and its copy with the blue head. */
export const KNOWN_ORIGINALS = [STOCK_SHA256, SYNTH_SHA256, HACKTRIBE_SHA256, HACKTRIBE_BLUE_SHA256];

/**
 * Whether the original of a file with BLECH on it can be rebuilt from Korg's System Updater: only for Korg's own build.
 * Hacktribe changes bytes inside the places BLECH writes to as well (107 of its changed runs overlap the BLECH
 * patches, measured on Hacktribe 2.02 against Korg's red 2.02), and those bytes are in no file the app can load.
 */
export const canRestore = bytes => buildOf(bytes) !== "hacktribe";

/**
 * The unpatched original of `patched` (a file BLECH was put on before, for example by copying it to the card), rebuilt
 * from Korg's own 2.02 of the same Electribe: `patches` go on `korg` to learn which bytes they write (their spans and
 * whatever else they change, such as appended effect presets), and those bytes are copied from `korg` into the copy of
 * `patched`. The result counts only when its hash is one of `hashes` (the files the patcher takes as an original).
 * {ok: true, bytes, sha256}, or {ok: false, why: "size" | "patches" | "mismatch"}; nothing is guessed.
 */
export async function restoreOriginal(patched, korg, patches, { hashes = KNOWN_ORIGINALS } = {}) {
  if (patched.length !== VSB_SIZE || korg.length !== VSB_SIZE) return { ok: false, why: "size" };
  const applied = await applyPatches(korg, patches);
  if (!applied.ok) return { ok: false, why: "patches" };
  const out = Uint8Array.from(patched);
  const restore = (from, to) => out.set(korg.subarray(from, to), from);
  for (const s of applied.spans) restore(s.file, s.file + s.length);
  let from = -1;
  for (let i = 0; i <= VSB_SIZE; i++) {
    const differs = i < VSB_SIZE && applied.bytes[i] !== korg[i];
    if (differs && from < 0) from = i;
    else if (!differs && from >= 0) { restore(from, i); from = -1; }
  }
  const hash = await sha256(out);
  return hashes.includes(hash) ? { ok: true, bytes: out, sha256: hash } : { ok: false, why: "mismatch" };
}

/** The folder below KORG/ the firmware of this kind keeps its files in (the stock firmware's has a space). Hacktribe on the blue reads KORG/hacktribe like on the red. */
const FOLDER = { stock: "electribe sampler", synth: "electribe" };
export const BLECH_FOLDER = "blechtribe";

/** Doom for the card (third_party/doom, docs/doom-lizenz.md): offered when the set carries the loader that reads it. */
export const DOOM_FOLDER = `KORG/${BLECH_FOLDER}/Doom/`;
export const DOOM_FILES = ["third_party/doom/doom.bin", "third_party/doom/doom.wad"];
export const hasDoom = blech => blech.items.some(p => p.id === "doom-loader");

/** Where the firmware that runs on the device when it updates looks for SYSTEM.VSB on the card. */
export function cardFolder(kind) {
  return `KORG/${FOLDER[kind] ?? "hacktribe"}/System/`;
}

/** The folder with the user's samples and patterns now, which BLECH does not read (it reads KORG/blechtribe/). */
export function sampleFolder(kind) {
  return `KORG/${FOLDER[kind] ?? "hacktribe"}/`;
}

/**
 * The report for a patched copy that is byte for byte one that already passed the check (`verified`, the parsed
 * data/patches/verified.json), or null. The same input and the same result give the same boots, so the check need not
 * run again: on a slow PC it takes more than an hour.
 */
export async function verifiedReport(input, output, verified, hardware = null) {
  const results = verified?.format === "gelumpe-verified" && verified.version === 1 && Array.isArray(verified.results) ? verified.results : [];
  if (!results.length) return null;
  const [from, to] = await Promise.all([sha256(input), sha256(output)]);
  // the same files on the other hardware boot from another flash: that is another check
  const hit = results.find(r => r.input === from && r.output === to && (r.hardware ?? null) === hardware);
  if (!hit) return null;
  return {
    ok: true, verified: true, changed: [],
    checks: [{ id: "verified", ok: true, detail: text("patcher.checkDetail.verified", { date: hit.date, checks: hit.checks }) }],
  };
}

/** Keys of the names for the checks of tools/emu/check.py. */
const CHECK_NAMES = {
  header: "patcher.checkName.header",
  dsp_stream: "patcher.checkName.dspStream",
  dsp_boot_once: "patcher.checkName.dspBootOnce",
  "boot:normal": "patcher.checkName.bootNormal",
  "boot:normal_blank": "patcher.checkName.bootNormalBlank",
  update_offer: "patcher.checkName.updateOffer",
  panel_update: "patcher.checkName.panelUpdate",
  kill_switch: "patcher.checkName.killSwitch",
  start_phase: "patcher.checkName.startPhase",
  start_phase_exceptions: "patcher.checkName.startPhaseExceptions",
  verified: "patcher.checkName.verified",
  quick: "patcher.checkName.quick",
};

/** The name of a check as a text; an unknown id stays as it is. */
export function checkName(id) {
  if (id.startsWith("start_mode:")) return text("patcher.checkName.startMode");
  return CHECK_NAMES[id] ? text(CHECK_NAMES[id]) : id;
}

export function checkDetail(detail) {
  if (typeof detail === "string" || isText(detail)) return detail;
  const where = (kind, hits) => hits.map(([at, n]) => text(kind, { at, n }));
  const spots = [...where("patcher.checkDetail.code", detail?.code ?? []), ...where("patcher.checkDetail.data", detail?.data ?? [])];
  return text("patcher.checkDetail.startPhase", { spots: spots.length ? spots.reduce((a, b) => text("patcher.checkDetail.join", { a, b })) : "" });
}

// ---- progress of the emulator check -------------------------------------------------------------

/** The bar never reads 100 before the real result is in. */
export const CHECK_HOLD = 99;

/**
 * What the page shows for one progress snapshot of the emulator service (tools/emu/progress.py): the bar (0 to
 * `CHECK_HOLD`), one line of text, and the groups with a short state each. A snapshot that is not a running one
 * (idle, or left over from the run before) gives null.
 * @returns {{value: number, text: string, groups: {id: string, name: string, state: string, text: string}[]} | null}
 */
export function checkProgress(snapshot) {
  if (!snapshot || snapshot.state !== "running" || !(snapshot.total > 0)) return null;
  const groupText = g => g.state === "done" ? `${g.ok}/${g.ok + g.fail}` : g.state === "failed" ? text("patcher.group.failed", { count: g.fail }) : g.state === "running" ? text("patcher.group.running") : "";
  return {
    value: Math.min(CHECK_HOLD, Math.round(100 * snapshot.done / snapshot.total)),
    text: text("patcher.progress.count", { done: snapshot.done, total: snapshot.total }),
    groups: snapshot.groups.map(g => ({ id: g.id, name: g.name, state: g.state, text: groupText(g) })),
  };
}

/** m:ss for a duration in ms. */
export function clock(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// ---- the run, from drop to download --------------------------------------------------------------

/**
 * phase: empty, rejected, needs-patch (Korg's original on the Hacktribe route, waiting for the user's hacktribe-2.patch),
 * ready, patching, checking, passed, failed, downloaded. origin: what the user dropped (stock, hacktribe or synth), for the card
 * folder. route: for Korg's original, "direct" (BLECH straight onto it) or "hacktribe" (hacktribe-2.patch first).
 * device: the Electribe the copy is for, "red" or "blue"; asked for every copy with Hacktribe (`choosesDevice`).
 * steps: the pass list, status todo|ok|error.
 */
/** The four steps of the way the page shows above everything (firmware, patches, emulator, device), each todo, current, done or error. */
export const WAY = ["patcher.way.firmware", "patcher.way.patches", "patcher.way.test", "patcher.way.device"];
export function wayOf(flow) {
  const at = { empty: 0, rejected: 0, "needs-patch": 1, ready: 1, patching: 1, checking: 2, failed: 2, passed: 3, downloaded: 4 }[flow.phase] ?? 0;
  const bad = flow.phase === "rejected" ? 0 : flow.phase === "failed" ? (flow.report ? 2 : 1) : -1;
  return WAY.map((key, i) => ({ label: text(key), state: i === bad ? "error" : i < at ? "done" : i === at ? "current" : "todo" }));
}

export const newFlow = () => ({ phase: "empty", input: null, origin: null, route: null, device: null, steps: [], report: null, error: null });

/** Whether the copy carries Hacktribe, which runs on the red and the blue alike: then the user says which one it is for. */
export const choosesDevice = flow => flow.origin === "hacktribe" || (flow.origin === "stock" && flow.route === "hacktribe");

/**
 * The head the patches go on, or null to leave it. Hacktribe already running (a Hacktribe file dropped) takes the Sampler
 * head on either Electribe; Korg's firmware running on the blue (Korg's red file turned into Hacktribe for the blue)
 * takes only the blue one (docs/messungen/2026-10-26-blech-hacktribe-blau.md).
 */
export function headFor(flow) {
  if (flow.origin === "hacktribe") return flow.input?.hardware === "blue" ? "sampler" : null;
  if (flow.origin === "stock" && flow.route === "hacktribe" && flow.device === "blue") return "blue";
  return null;
}

/** The card folder of the firmware that runs on the device when it takes this copy. */
export const folderOf = flow => cardFolder(flow.origin === "stock" && flow.device === "blue" ? "synth" : flow.origin);

const STOCK_READ = { id: "read", label: text("patcher.step.readStock"), status: "ok", detail: "" };

const RUNNING = new Set(["patching", "checking"]);
const mark = (steps, id, status, detail = "") => steps.map(s => (s.id === id ? { ...s, status, detail } : s));

/** One transition; an event that does not fit the phase leaves the state as it was. */
export function step(flow, event) {
  switch (event.type) {
    case "reset": return newFlow();
    case "input": {
      if (RUNNING.has(flow.phase)) return flow;
      const { input } = event;
      if (input.kind === "stock") return { ...newFlow(), phase: "ready", input, origin: "stock", route: "direct", device: "red", steps: [STOCK_READ] };
      if (input.kind === "synth") return { ...newFlow(), phase: "ready", input, origin: "synth", route: "direct", device: "blue", steps: [{ id: "read", label: text("patcher.step.readSynth"), status: "ok", detail: "" }] };
      if (input.kind !== "hacktribe") return { ...newFlow(), phase: "rejected", input };
      const blue = input.hardware === "blue";
      return { ...newFlow(), phase: "ready", input, origin: "hacktribe", device: blue ? "blue" : "red", steps: [{ id: "read", label: text(blue ? "patcher.step.readHacktribeBlue" : "patcher.step.readHacktribe"), status: "ok", detail: "" }] };
    }
    case "device": {
      // a copy made for the other Electribe is another copy: what was patched or checked goes
      if (!choosesDevice(flow) || RUNNING.has(flow.phase) || !["red", "blue"].includes(event.device) || event.device === flow.device) return flow;
      const done = ["passed", "downloaded", "failed"].includes(flow.phase);
      return { ...flow, device: event.device, ...(done ? { phase: "ready", report: null, error: null, untested: false, steps: flow.steps.filter(s => s.id === "read" || s.id === "convert") } : {}) };
    }
    case "options": {
      // another choice of optional patches is another copy: what was patched or checked goes, as with the device
      if (RUNNING.has(flow.phase) || !["passed", "downloaded", "failed"].includes(flow.phase)) return flow;
      return { ...flow, phase: "ready", report: null, error: null, untested: false, steps: flow.steps.filter(s => s.id === "read" || s.id === "convert") };
    }
    case "route": {
      // `event.input` is Korg's original again, whichever route the file was on
      if (flow.origin !== "stock" || RUNNING.has(flow.phase) || !["direct", "hacktribe"].includes(event.route)) return flow;
      const direct = event.route === "direct";
      return { ...newFlow(), phase: direct ? "ready" : "needs-patch", input: event.input, origin: "stock", route: event.route, device: direct ? "red" : flow.device ?? "red", steps: direct ? [STOCK_READ] : [] };
    }
    case "converted": {
      if (flow.phase !== "needs-patch") return flow;
      return {
        ...newFlow(), phase: "ready", input: event.input, origin: "stock", route: "hacktribe", device: flow.device ?? "red",
        steps: [
          STOCK_READ,
          { id: "convert", label: text("patcher.step.convert"), status: "ok", detail: event.detail ?? "" },
        ],
      };
    }
    case "convert-failed":
      return flow.phase === "needs-patch" ? { ...flow, error: event.message } : flow;
    case "patching": {
      if (!allowed(flow).patch) return flow;
      const base = flow.steps.filter(s => s.id === "read" || s.id === "convert");
      const head = headFor(flow);
      const headStep = head ? [{ id: "head", label: text(head === "blue" ? "patcher.step.headBlue" : "patcher.step.headSampler"), status: "ok", detail: head === "blue" ? "Byte 0x12 = 0x00, 0x2E = 0x23" : "Byte 0x12 = 0x53, 0x2E = 0x24" }] : [];
      return {
        ...flow, phase: "patching", report: null, error: null, untested: false,
        steps: [...base, ...headStep, ...event.patches.map(p => ({ id: `patch:${p.id}`, label: p.label, status: "todo", detail: "" })), { id: "check", label: text("patcher.step.check"), status: "todo", detail: "" }],
      };
    }
    case "patch":
      if (flow.phase !== "patching") return flow;
      return { ...flow, steps: mark(flow.steps, `patch:${event.id}`, event.ok ? "ok" : "error", event.detail) };
    case "checking":
      if (flow.phase !== "patching" || flow.steps.some(s => s.id.startsWith("patch:") && s.status !== "ok")) return flow;
      return { ...flow, phase: "checking" };
    case "untested":
      // the user chose no test and took on what follows: the copy goes on without a report
      if (flow.phase !== "patching" || flow.steps.some(s => s.id.startsWith("patch:") && s.status !== "ok")) return flow;
      return { ...flow, phase: "passed", untested: true, steps: mark(flow.steps, "check", "skip", text("patcher.step.untested")) };
    case "recheck":
      // the thorough check of a copy that passed the quick one
      if (flow.phase !== "passed" && flow.phase !== "downloaded") return flow;
      return { ...flow, phase: "checking", report: null, error: null, steps: mark(flow.steps, "check", "todo") };
    case "checked": {
      if (flow.phase !== "checking") return flow;
      const bad = event.report.checks.filter(c => !c.ok).length;
      const detail = text(bad ? "patcher.step.checkFailed" : "patcher.step.checkPassed", { count: bad || event.report.checks.length, total: event.report.checks.length });
      const ok = event.report.ok === true && !bad;
      return { ...flow, phase: ok ? "passed" : "failed", report: event.report, steps: mark(flow.steps, "check", ok ? "ok" : "error", detail) };
    }
    case "error": {
      if (!RUNNING.has(flow.phase)) return flow;
      const open = flow.steps.find(s => s.status === "todo" || s.status === "error");
      return { ...flow, phase: "failed", error: event.message, steps: open ? mark(flow.steps, open.id, "error", event.message) : flow.steps };
    }
    case "downloaded":
      return flow.phase === "passed" || flow.phase === "downloaded" ? { ...flow, phase: "downloaded" } : flow;
    default: return flow;
  }
}

/** "blue" for Sampler code on the blue (Hacktribe for the blue), which the emulator check cannot tell from a Sampler head; the synth build it knows itself. */
export const hardwareOfFlow = flow => (flow.device === "blue" && flow.origin !== "synth" ? "blue" : null);

/** What the buttons may do now. The download and the emulator test only exist for a copy that passed the check. */
export function allowed(flow) {
  const done = flow.phase === "passed" || flow.phase === "downloaded";
  // an untested copy may still be patched again, with a test this time
  return { patch: flow.phase === "ready" || flow.phase === "failed" || (done && !!flow.untested), download: done, test: done, busy: RUNNING.has(flow.phase) };
}
