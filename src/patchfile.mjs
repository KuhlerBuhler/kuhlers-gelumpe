/**
 * One file for a whole patch set, for handing out (docs/patcher.md, "Patch-Datei").
 *
 *   offset  size  what
 *        0     8  magic "GLMPPAT\0"
 *        8     2  format version, 2 (little endian, like all numbers here)
 *       10     2  flags, 0
 *       12     4  payload length
 *       16    16  set version as text (BLECH 1.0.0), NUL padded
 *       32    32  fingerprint of the SYSTEM.VSB the set is made for (below)
 *       64    32  fingerprint of the SYSTEM.VSB it produces
 *       96    32  sha256 of the payload
 *      128     n  payload: JSON { format: "gelumpe-patch-file", id, name, userData: [[file, length], ...], patches: [...],
 *                      alternates: { stock: { input, output }, "hacktribe-blue": { input, output },
 *                                    synth: { input, output, patches: [...] } } }
 *
 * The two fingerprints in the head are for Hacktribe 2.02. `alternates` names the other firmwares the file takes, each
 * with the same two fingerprints for that firmware: Korg's own 2.02 (`stock`, the same patches, which carry a variant per
 * build, `builds` in src/patch.mjs), Hacktribe with the blue Electribe's head (`hacktribe-blue`, the same patches; only
 * the head is different, and the fingerprint covers it) and the blue Electribe's own 2.02 (`synth`, with its own list:
 * the synth set has fewer patches).
 *
 * The fingerprint of an image is the sha256 of all its bytes except the
 * `userData` ranges: the data this editor and other tools change in a VSB
 * (FX presets, the menu lengths, the start image, the groove and modulation
 * tables). Any Hacktribe 2.02 whose code and fixed data match is accepted,
 * whoever edited the rest. The fingerprint of the output leaves out only the
 * `userData` bytes the patches do not write, so what the patches write is
 * checked as well.
 *
 * The patches are the very objects src/patch.mjs applies, with their hooks,
 * start-phase exceptions and the hashes of the bytes they replace, which are
 * still checked one by one. Applying the file is applyPatches over that list
 * between the two fingerprint checks, so the result is byte for byte what
 * applying the set gives. Nothing here carries firmware: the hashes name bytes,
 * they do not hold them. What stays in the file is what the patches already
 * carry, namely our own code and the displaced instruction words our hook code
 * replays at a hook site.
 */
import { applyPatches, fromHex, selectFor, toHex } from "./patch.mjs";
import { buildOf, hardwareOf, sha256 } from "./firmware.mjs";
import { FIELDS, TABLES, byteSpans } from "./map/index.mjs";
import { tableEntry } from "./map/address.mjs";

export const PATCH_FILE_MAGIC = "GLMPPAT\0";
export const PATCH_FILE_VERSION = 2;
export const PATCH_FILE_FORMAT = "gelumpe-patch-file";
export const PATCH_FILE_HEADER = 128;
/** The firmwares a patch file can name besides Hacktribe 2.02 (the head), as keys of `alternates`. */
export const ALTERNATES = ["stock", "hacktribe-blue", "synth"];
const VERSION_WIDTH = 16;
const IMAGE = 0x200100;
const FIRST = 0x100;

const ascii = text => Uint8Array.from(text, c => c.charCodeAt(0));
const MAGIC = ascii(PATCH_FILE_MAGIC);
const sha = async bytes => fromHex(await sha256(bytes));

/** Whether these bytes start like a patch file. */
export function isPatchFile(bytes) {
  return bytes.length >= MAGIC.length && MAGIC.every((b, i) => bytes[i] === b);
}

/** Sorted, merged [start, end) ranges from any list of them. */
function merge(ranges) {
  const out = [];
  for (const [start, end] of [...ranges].sort((a, b) => a[0] - b[0])) {
    const last = out.at(-1);
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else out.push([start, end]);
  }
  return out;
}

/** What `ranges` still cover after the spans a patch writes are taken out of them. */
function without(ranges, spans) {
  let rest = merge(ranges);
  for (const { file, length } of spans) {
    rest = rest.flatMap(([start, end]) => {
      if (file + length <= start || file >= end) return [[start, end]];
      return [[start, Math.min(end, file)], [Math.max(start, file + length), end]].filter(([a, b]) => b > a);
    });
  }
  return rest;
}

/** sha256 over every byte of the image outside the [start, end) ranges. */
export async function fingerprint(bytes, ranges) {
  const parts = [];
  let at = 0;
  for (const [start, end] of merge(ranges)) {
    parts.push(bytes.subarray(at, start));
    at = end;
  }
  parts.push(bytes.subarray(at));
  const joined = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let to = 0;
  for (const p of parts) { joined.set(p, to); to += p.length; }
  return sha256(joined);
}

/**
 * What a VSB of this firmware lets users change, as [file, length] ranges,
 * read from the device map: the tables whose fields are writable in the
 * firmware (FX presets, grooves, modulation types) and the writable fields of
 * the firmware block itself (menu lengths, start image).
 */
export function userDataRanges() {
  const writable = f => f.transport.includes("firmware") && f.edit !== "readonly";
  const blocks = new Set([...FIELDS.values()].filter(writable).map(f => f.block));
  const ranges = [];
  for (const t of TABLES.values()) {
    if (!blocks.has(t.block)) continue;
    const last = tableEntry(t.id, t.count - 1);
    ranges.push([t.file, last.file + last.size]);
  }
  for (const f of FIELDS.values()) if (writable(f) && f.block === "firmware") ranges.push(...byteSpans(f));
  return merge(ranges).map(([start, end]) => [start, end - start]);
}

const asRanges = list => list.map(([file, length]) => [file, file + length]);

/**
 * The patch file for a set: applies it to `vsb` first, so the output
 * fingerprint is the real one and a set that does not apply is never written.
 * @param {Uint8Array} vsb a firmware the set is made for
 * @param {object[]} patches the patches in the order they are applied
 * @param {{version: string, id?: string, name?: string, userData?: number[][], stock?: Uint8Array, synth?: Uint8Array, synthPatches?: object[]}} meta
 *   `stock` is Korg's own 2.02, `synth` the blue Electribe's own 2.02 with `synthPatches`, its set; Hacktribe with the
 *   blue head is always named, made from `vsb`
 */
export async function buildPatchFile(vsb, patches, { version, id = "patch-set", name = id, userData = userDataRanges(), stock, synth, synthPatches } = {}) {
  if (typeof version !== "string" || !/^[\x21-\x7e]{1,16}$/.test(version)) throw new TypeError("version is 1 to 16 printable characters");
  if (buildOf(vsb) !== "hacktribe" || hardwareOf(vsb) !== "red") throw new TypeError("the head names Hacktribe 2.02 with the Sampler head, give Korg's own as `stock` or `synth`");
  const applied = await applyPatches(vsb, patches);
  if (!applied.ok) throw new Error(`the set does not apply:\n${applied.reasons.join("\n")}`);
  const pair = async (input, list, label) => {
    const done = await applyPatches(input, list);
    if (!done.ok) throw new Error(`the set does not apply to ${label}:\n${done.reasons.join("\n")}`);
    return { input: await fingerprint(input, asRanges(userData)), output: await fingerprint(done.bytes, without(asRanges(userData), done.spans)) };
  };
  const blue = Uint8Array.from(vsb);
  blue.set([0x00], 0x12);
  blue.set([0x23], 0x2e);
  // only Hacktribe's own code stays Hacktribe under the blue head (src/firmware.mjs, buildOf)
  const alternates = buildOf(blue) === "hacktribe" ? { "hacktribe-blue": await pair(blue, patches, "Hacktribe with the blue head") } : {};
  if (stock) {
    if (buildOf(stock) !== "stock") throw new TypeError("`stock` is not Korg's own 2.02");
    alternates.stock = await pair(stock, patches, "Korg's own 2.02");
  }
  if (synth) {
    if (buildOf(synth) !== "synth" || !Array.isArray(synthPatches) || !synthPatches.length) throw new TypeError("`synth` is the blue Electribe's own 2.02, with `synthPatches`");
    alternates.synth = { ...await pair(synth, synthPatches, "the blue Electribe's own 2.02"), patches: synthPatches };
  }
  const payload = new TextEncoder().encode(JSON.stringify({ format: PATCH_FILE_FORMAT, id, name, userData, patches, ...(Object.keys(alternates).length ? { alternates } : {}) }));
  const out = new Uint8Array(PATCH_FILE_HEADER + payload.length);
  const view = new DataView(out.buffer);
  out.set(MAGIC, 0);
  view.setUint16(8, PATCH_FILE_VERSION, true);
  view.setUint32(12, payload.length, true);
  out.set(ascii(version), 16);
  out.set(fromHex(await fingerprint(vsb, asRanges(userData))), 32);
  out.set(fromHex(await fingerprint(applied.bytes, without(asRanges(userData), applied.spans))), 64);
  out.set(await sha(payload), 96);
  out.set(payload, PATCH_FILE_HEADER);
  return out;
}

/**
 * Reads and checks a patch file. Throws an Error that says what is wrong.
 * @returns {Promise<{formatVersion: number, version: string, input: string, output: string, id: string, name: string, userData: number[][], patches: object[], alternates: object}>}
 */
export async function parsePatchFile(bytes) {
  if (!isPatchFile(bytes)) throw new Error("keine Patch-Datei (die Kennung am Anfang fehlt)");
  if (bytes.length < PATCH_FILE_HEADER) throw new Error("die Patch-Datei ist zu kurz");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const formatVersion = view.getUint16(8, true);
  if (formatVersion !== PATCH_FILE_VERSION) throw new Error(`Patch-Datei in Format ${formatVersion}, diese Version kennt nur ${PATCH_FILE_VERSION}`);
  if (view.getUint16(10, true) !== 0) throw new Error("die Patch-Datei setzt Merkmale, die diese Version nicht kennt");
  const length = view.getUint32(12, true);
  if (bytes.length !== PATCH_FILE_HEADER + length) throw new Error("die Länge im Kopf passt nicht zur Datei, sie ist abgeschnitten oder verändert");
  const payload = bytes.subarray(PATCH_FILE_HEADER);
  if (toHex(await sha(payload)) !== toHex(bytes.subarray(96, 128))) throw new Error("die Prüfsumme der Patch-Datei stimmt nicht, sie ist beschädigt");
  const versionBytes = bytes.subarray(16, 16 + VERSION_WIDTH);
  const end = versionBytes.indexOf(0);
  const version = String.fromCharCode(...versionBytes.subarray(0, end < 0 ? VERSION_WIDTH : end));
  let body;
  try { body = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(payload)); } catch { throw new Error("der Inhalt der Patch-Datei ist kein JSON"); }
  if (body?.format !== PATCH_FILE_FORMAT || !Array.isArray(body.patches) || !body.patches.length) throw new Error("der Inhalt ist kein Patch-Satz");
  const ok = r => Array.isArray(r) && r.length === 2 && r.every(Number.isInteger) && r[0] >= FIRST && r[1] > 0 && r[0] + r[1] <= IMAGE;
  if (!Array.isArray(body.userData) || !body.userData.every(ok)) throw new Error("userData ist eine Liste von [Datei, Länge] im Abbild");
  const alternates = body.alternates ?? {};
  const hex64 = h => typeof h === "string" && /^[0-9a-f]{64}$/.test(h);
  const fits = ([k, v]) => ALTERNATES.includes(k) && hex64(v?.input) && hex64(v?.output)
    && (k === "synth" ? Array.isArray(v.patches) && v.patches.length > 0 : v.patches === undefined);
  if (typeof alternates !== "object" || Array.isArray(alternates) || !Object.entries(alternates).every(fits)) {
    throw new Error(`alternates nennt nur ${ALTERNATES.join(", ")}, mit input und output als sha256 (synth mit eigenen patches)`);
  }
  return {
    formatVersion, version,
    input: toHex(bytes.subarray(32, 64)),
    output: toHex(bytes.subarray(64, 96)),
    id: body.id, name: body.name, userData: body.userData, patches: body.patches, alternates,
  };
}

const FIRMWARE_NAMES = { hacktribe: "Hacktribe 2.02", stock: "Korgs Original 2.02", "hacktribe-blue": "Hacktribe 2.02 für die blaue Electribe", synth: "Korgs 2.02 der blauen Electribe" };

/** Which of the head's firmware or of `alternates` a VSB is. */
const firmwareKey = vsb => {
  const build = buildOf(vsb);
  return build === "hacktribe" && hardwareOf(vsb) === "blue" ? "hacktribe-blue" : build;
};

/** The patches of a parsed patch file that go onto this VSB, one variant per patch (what the page lists). */
export function patchesFor(file, vsb) {
  const key = firmwareKey(vsb);
  const list = key === "synth" ? file.alternates.synth?.patches ?? [] : file.patches;
  return selectFor(list, buildOf(vsb)).patches;
}

/**
 * A patch file applied to a copy of the user's VSB: the same result as
 * applyPatches over the set, plus `file` (the header) when it worked.
 * Refused before anything is written when the VSB differs from what the file
 * names outside its userData, and again when what comes out is not the output
 * the file names.
 */
export async function applyPatchFile(vsb, bytes) {
  const none = reasons => ({ ok: false, reasons, dependencies: [], spans: [], allow: [], allowCode: [] });
  let file;
  try { file = await parsePatchFile(bytes); } catch (error) { return none([error.message]); }
  if (vsb.length !== IMAGE) return none([`Die Datei ist ${vsb.length} Byte groß; eine SYSTEM.VSB für 2.02 hat ${IMAGE}.`]);
  const userData = asRanges(file.userData);
  const key = firmwareKey(vsb);
  const target = key === "hacktribe" ? { input: file.input, output: file.output } : file.alternates[key];
  if (!target) return none([`${file.name} ${file.version} ist nicht für ${FIRMWARE_NAMES[key]} gebaut.`]);
  const input = await fingerprint(vsb, userData);
  if (input !== target.input) {
    return none([`Das ist keine SYSTEM.VSB, auf die ${file.name} ${file.version} passt: Code oder feste Daten weichen von ${FIRMWARE_NAMES[key]} ab (Fingerabdruck ohne FX-Presets, Menülängen, Startbild und Tabellen: erwartet ${target.input}, gefunden ${input}).`]);
  }
  const applied = await applyPatches(vsb, target.patches ?? file.patches);
  if (!applied.ok) return applied;
  const output = await fingerprint(applied.bytes, without(userData, applied.spans));
  if (output !== target.output) {
    return none([`Das Ergebnis stimmt nicht mit der Patch-Datei überein (Fingerabdruck erwartet ${target.output}, entstanden ${output}).`]);
  }
  const { patches, ...header } = file;
  return { ...applied, file: header };
}
