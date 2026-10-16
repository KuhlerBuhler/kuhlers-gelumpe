/**
 * A SYSTEM.VSB, the firmware image the device boots from.
 *
 * The file is never shipped with this project and never committed: it is
 * Korg's. Point the tools at your own copy.
 */
import {
  TABLE, RECORD_SIZE, MFX_COUNT_RAM, IFX_COUNT_FILE, IFX_LAST_INDEX_FILE, ramToFile,
} from "./layout.mjs";
import { FxRecord } from "./record.mjs";
import { recordOf, presetRoom } from "./presets.mjs";
import { loadUnits, unitFor } from "./units.mjs";

/**
 * The slot tables are sized generously and the space past the last preset
 * holds whatever else the firmware keeps there. A record only counts as a
 * preset when its name is something the display could show and its first
 * stage names a unit we know.
 */
function looksLikePreset(record) {
  const name = record.name;
  if (!name) return false;
  for (const ch of name) {
    const c = ch.charCodeAt(0);
    if (c < 0x20 || c > 0x7e) return false;
  }
  const units = loadUnits();
  const first = record.stageNames[0];
  const kind = first === "mfx" ? "mfx" : "ifx";
  return !!unitFor(units, kind, record.device(first));
}

export class VsbImage {
  constructor(buffer) {
    this.bytes = Uint8Array.from(buffer);
  }

  /** A cheap fingerprint, enough to tell two images apart in a report. */
  get fingerprint() {
    let a = 0x811c9dc5;
    for (let i = 0; i < this.bytes.length; i++) {
      a ^= this.bytes[i];
      a = Math.imul(a, 0x01000193) >>> 0;
    }
    return a.toString(16).padStart(8, "0");
  }

  slotOffset(kind, slot) {
    const table = TABLE[kind];
    if (!table) throw new Error(`unknown table ${kind}`);
    const found = recordOf(this.bytes, kind, slot);
    if (found) return found.file;
    if (slot < 1 || slot > table.slots) throw new Error(`${kind} slot ${slot} out of range`);
    return ramToFile(table.ram) + (slot - 1) * RECORD_SIZE;
  }

  read(kind, slot) {
    const at = this.slotOffset(kind, slot);
    return new FxRecord(this.bytes.subarray(at, at + RECORD_SIZE), kind);
  }

  write(kind, slot, record) {
    if (record.kind !== kind) throw new Error(`a ${record.kind} record cannot go in the ${kind} table`);
    this.bytes.set(record.bytes, this.slotOffset(kind, slot));
  }

  /** Every slot that carries a name, which is how the device decides it exists. */
  list(kind) {
    const out = [];
    const seen = new Set();
    const last = presetRoom(this.bytes, kind)?.capacity ?? TABLE[kind].slots;
    for (let slot = 1; slot <= last; slot++) {
      const at = this.slotOffset(kind, slot);
      if (seen.has(at)) continue;      // an entry of the patch's array that still points at an earlier record
      seen.add(at);
      const rec = this.read(kind, slot);
      if (!looksLikePreset(rec)) continue;
      out.push({ slot, name: rec.name, record: rec });
    }
    return out;
  }

  get mfxCount() { return this.bytes[ramToFile(MFX_COUNT_RAM)]; }
  set mfxCount(n) { this.bytes[ramToFile(MFX_COUNT_RAM)] = n & 0xff; }

  /**
   * The insert menu length, written to all thirteen places that hold it.
   * Reading returns the count sites; a disagreement between sites is a fault
   * worth knowing about, so it is reported rather than hidden.
   */
  get ifxCount() {
    const counts = IFX_COUNT_FILE.map(a => this.bytes[a]);
    const last = IFX_LAST_INDEX_FILE.map(a => this.bytes[a]);
    const agreed = counts.every(c => c === counts[0]) && last.every(l => l === counts[0] - 1);
    return { value: counts[0], agreed, counts, last };
  }

  set ifxCount(n) {
    for (const a of IFX_COUNT_FILE) this.bytes[a] = n & 0xff;
    for (const a of IFX_LAST_INDEX_FILE) this.bytes[a] = (n - 1) & 0xff;
  }
}
