/**
 * Any patch file the Patcher can lay over a SYSTEM.VSB: the page's own patch file (src/patchfile.mjs), a gelumpe-patch
 * in JSON, an IPS patch (PATCH and IPS32) and a bsdiff patch (BSDIFF40). Reading says which one a file is, or why it is none;
 * applying gives the same result shape as applyPatches, so the page checks and saves it like a BLECH patch.
 * Formats this file knows by their magic but does not apply (BPS, UPS, xdelta) are named in the error.
 */
import { applyPatchFile, parsePatchFile, patchesFor } from "./patchfile.mjs";
import { applyPatches, PATCH_FORMAT } from "./patch.mjs";
import { applyBsdiff, parseBsdiff } from "./bsdiff.mjs";
import { VSB_SIZE } from "./patcher.mjs";
import { text, TextError } from "./text.mjs";

/** The id of the one item a patch that is no patch file lists. */
export const OWN_ID = "own-patch";

/** Formats named by their first bytes that the patcher does not apply. */
const UNSUPPORTED = [["BPS1", "BPS"], ["UPS1", "UPS"], ["\xd6\xc3\xc4", "xdelta"], ["MOD0", "MOD"]];

const startsWith = (bytes, magic) => bytes.length >= magic.length && [...magic].every((c, i) => bytes[i] === c.charCodeAt(0));

/** Reads an IPS (or IPS32) patch into its records, and the length it cuts the file to when it says so. */
function parseIps(bytes, wide) {
  const idWidth = wide ? 4 : 3;
  const end = wide ? "EEOF" : "EOF";
  const records = [];
  let at = 5;
  const bad = () => new TextError("patcher.any.ips.bad");
  const number = width => {
    if (at + width > bytes.length) throw bad();
    let n = 0;
    for (let i = 0; i < width; i++) n = n * 256 + bytes[at + i];
    at += width;
    return n;
  };
  for (;;) {
    if (startsWith(bytes.subarray(at), end) && bytes.length - at >= end.length) { at += end.length; break; }
    const offset = number(idWidth);
    const size = number(2);
    if (size === 0) {
      const length = number(2);
      if (at >= bytes.length) throw bad();
      records.push({ offset, length, fill: bytes[at++] });
    } else {
      if (at + size > bytes.length) throw bad();
      records.push({ offset, length: size, data: bytes.subarray(at, at + size) });
      at += size;
    }
  }
  let cut = null;
  if (bytes.length - at === idWidth) cut = number(idWidth);
  else if (at !== bytes.length) throw bad();
  if (!records.length) throw bad();
  return { records, cut };
}

/** The runs of bytes that differ between two images of the same length, as spans. */
function changed(from, to) {
  const spans = [];
  let start = -1;
  for (let i = 0; i <= to.length; i++) {
    const differs = i < to.length && to[i] !== from[i];
    if (differs && start < 0) start = i;
    if (!differs && start >= 0) { spans.push({ patch: OWN_ID, file: start, length: i - start, field: null }); start = -1; }
  }
  return spans;
}

/**
 * What a patch file is. Throws a TextError that says why it is no patch the patcher reads.
 * @returns {Promise<{kind: "gelumpe" | "json" | "ips" | "bsdiff", label: object, bytes: Uint8Array, file?: object, patches?: object[]}>}
 */
export async function readAnyPatch(bytes) {
  if (!bytes.length) throw new TextError("patcher.any.empty");
  if (startsWith(bytes, "GLMPPAT\0")) {
    const file = await parsePatchFile(bytes);
    return { kind: "gelumpe", bytes, file, label: text("patcher.any.label.gelumpe", { name: file.name, version: file.version }) };
  }
  if (startsWith(bytes, "BSDIFF40")) {
    parseBsdiff(bytes);
    return { kind: "bsdiff", bytes, label: text("patcher.any.label.bsdiff") };
  }
  if (startsWith(bytes, "IPS32") || startsWith(bytes, "PATCH")) {
    const wide = startsWith(bytes, "IPS32");
    const { records } = parseIps(bytes, wide);
    return { kind: "ips", bytes, wide, label: text("patcher.any.label.ips", { count: records.length }) };
  }
  for (const [magic, format] of UNSUPPORTED) if (startsWith(bytes, magic)) throw new TextError("patcher.any.unsupported", { format });
  const first = bytes.find(b => b !== 0x20 && b !== 0x0a && b !== 0x0d && b !== 0x09);
  if (first === 0x7b || first === 0x5b) {
    let body;
    try { body = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); } catch { throw new TextError("patcher.any.json"); }
    const patches = Array.isArray(body) ? body : [body];
    if (!patches.length || !patches.every(p => p?.format === PATCH_FORMAT && Array.isArray(p.changes))) throw new TextError("patcher.any.json");
    return { kind: "json", bytes, patches, label: text("patcher.any.label.json", { count: patches.length }) };
  }
  throw new TextError("patcher.any.unknown");
}

/** A patch that is not ours (IPS, bsdiff): it names no start-phase exceptions, so the emulator check leaves out the start phase. */
export const isForeign = own => own?.kind === "ips" || own?.kind === "bsdiff";

/** The items a plan lists for a read patch on the VSB `vsb`, `label` makes the text of a patch of a patch file. */
export function itemsOf(own, vsb, label) {
  if (own.kind === "gelumpe") return patchesFor(own.file, vsb).map(p => ({ id: p.id, label: label(p) }));
  if (own.kind === "json") return own.patches.map(p => ({ id: p.id, label: label(p) }));
  return [{ id: OWN_ID, label: own.label }];
}

/** `own` (from readAnyPatch) laid over `vsb`: {ok, bytes, reasons, dependencies, spans, allow, allowCode}. */
export async function applyAnyPatch(vsb, own) {
  const none = reasons => ({ ok: false, reasons, dependencies: [], spans: [], allow: [], allowCode: [] });
  if (own.kind === "gelumpe") return applyPatchFile(vsb, own.bytes);
  if (own.kind === "json") return applyPatches(vsb, own.patches);
  let out;
  try {
    if (own.kind === "bsdiff") out = applyBsdiff(vsb, own.bytes, { maxNewSize: VSB_SIZE });
    else {
      const { records, cut } = parseIps(own.bytes, own.wide);
      out = Uint8Array.from(vsb);
      for (const r of records) {
        if (r.offset + r.length > out.length) throw new TextError("patcher.any.ips.range", { offset: `0x${r.offset.toString(16)}` });
        if (r.data) out.set(r.data, r.offset);
        else out.fill(r.fill, r.offset, r.offset + r.length);
      }
      if (cut !== null && cut < out.length) out = out.slice(0, cut);
    }
  } catch (e) {
    return none([e.message]);
  }
  if (out.length !== VSB_SIZE) return none([new TextError("patcher.any.size", { size: out.length, expected: VSB_SIZE }).message]);
  return { ok: true, bytes: out, reasons: [], dependencies: [], spans: changed(vsb, out), allow: [], allowCode: [] };
}
