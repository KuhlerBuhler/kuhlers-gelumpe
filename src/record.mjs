/**
 * One effect preset.
 *
 * A record is 524 bytes and only part of it is understood. Five bytes follow
 * every device byte and twenty-three of the twenty-eight bytes in a map entry
 * mean nothing to us. They are not padding: a record built from zeros selects
 * on the device and then stays silent. So a preset is always an edit of a
 * record that came off the hardware or out of a firmware image, never a fresh
 * allocation. This class enforces that by only ever wrapping existing bytes.
 */
import { REC, RECORD_SIZE, MAP, STAGE_BLOCK_SIZE } from "./layout.mjs";
import { readName, writeName } from "./bytes.mjs";
import { unitFor } from "./units.mjs";

const STAGES = { mfx: ["mfx"], ifx: ["ifx1", "ifx2"] };

export class FxRecord {
  /** @param {Uint8Array} bytes a copy is taken; the caller keeps its own. */
  constructor(bytes, kind) {
    if (bytes.length !== RECORD_SIZE) {
      throw new Error(`record is ${bytes.length} bytes, expected ${RECORD_SIZE}`);
    }
    if (kind !== "mfx" && kind !== "ifx") throw new Error(`unknown kind ${kind}`);
    this.bytes = Uint8Array.from(bytes);
    this.kind = kind;
  }

  get stageNames() { return STAGES[this.kind]; }

  get name() {
    return readName(this.bytes.subarray(REC.name, REC.name + REC.nameWidth));
  }

  set name(text) {
    writeName(this.bytes, REC.name, String(text).slice(0, REC.nameWidth), REC.nameWidth);
  }

  get empty() { return this.device(this.stageNames[0]) === 0 && this.name === ""; }

  device(stage) { return this.bytes[REC.stage[stage].device]; }

  setDevice(stage, id) { this.bytes[REC.stage[stage].device] = id & 0xff; }

  /** Raw parameter value by position, ignoring what it is called. */
  paramAt(stage, index) { return this.bytes[REC.stage[stage].params + 2 * index]; }

  setParamAt(stage, index, value) {
    this.bytes[REC.stage[stage].params + 2 * index] = value & 0xff;
  }

  /** Parameters as name/value pairs, empty when the unit is unknown. */
  params(units, stage) {
    const unit = unitFor(units, stage === "mfx" ? "mfx" : "ifx", this.device(stage));
    if (!unit) return [];
    return unit.params.map(p => ({ ...p, value: this.paramAt(stage, p.index) }));
  }

  setParams(units, stage, values) {
    const unit = unitFor(units, stage === "mfx" ? "mfx" : "ifx", this.device(stage));
    if (!unit) throw new Error(`unknown device ${this.device(stage)} in ${stage}`);
    for (const [name, value] of Object.entries(values)) {
      const p = unit.params.find(x => x.name === name);
      if (!p) throw new Error(`${unit.unit} has no parameter ${name}`);
      this.setParamAt(stage, p.index, value);
    }
  }

  /**
   * Copy a whole stage block out of another record.
   *
   * The only safe way to change which unit sits in a stage. The five
   * undecoded bytes behind the device byte travel with it, and the block
   * lands in the same position it came from, never the other one: moving a
   * block between stage one and stage two produces a preset that is silent
   * on hardware.
   */
  adoptStage(stage, source, sourceStage = stage) {
    if (stage !== sourceStage) {
      throw new Error(
        `refusing to move a stage block from ${sourceStage} to ${stage}: ` +
        `stage blocks are position dependent`
      );
    }
    const at = REC.stage[stage].device;
    this.bytes.set(source.bytes.subarray(at, at + STAGE_BLOCK_SIZE), at);
  }

  /** The control map, only the entries that are switched on. */
  get map() {
    const rows = [];
    for (let i = 0; i < REC.mapEntries; i++) {
      const at = REC.map + i * REC.mapEntrySize;
      if (!this.bytes[at]) continue;
      rows.push({
        index: i,
        source: this.bytes[at + MAP.source],
        chain: this.bytes[at + MAP.chain],
        param: this.bytes[at + MAP.param],
        low: this.bytes[at + MAP.low],
        high: this.bytes[at + MAP.high],
      });
    }
    return rows;
  }

  /**
   * Room for `count` map rows. A free row takes the whole entry of a used one, here or in `donor`, before its five
   * known bytes are written: the other 23 are not understood, so a row is copied, never built from zeros.
   * @returns {boolean} false when neither record has a row to copy
   */
  growMap(count, donor = null) {
    const source = this.map.length ? this : donor?.map.length ? donor : null;
    if (!source) return count === 0;
    const from = REC.map + source.map.at(-1).index * REC.mapEntrySize;
    const row = source.bytes.slice(from, from + REC.mapEntrySize);
    for (let i = 0; i < Math.min(count, REC.mapEntries); i++) {
      const at = REC.map + i * REC.mapEntrySize;
      if (!this.bytes[at]) this.bytes.set(row, at);
    }
    return true;
  }

  set map(rows) {
    if (rows.length > REC.mapEntries) {
      throw new Error(`${rows.length} map rows, the record holds ${REC.mapEntries}`);
    }
    for (let i = 0; i < REC.mapEntries; i++) {
      const at = REC.map + i * REC.mapEntrySize;
      if (i >= rows.length) { this.bytes[at] = 0; continue; }
      const r = rows[i];
      this.bytes[at + MAP.source] = r.source & 0xff;
      this.bytes[at + MAP.chain] = r.chain & 0xff;
      this.bytes[at + MAP.param] = r.param & 0xff;
      this.bytes[at + MAP.low] = r.low & 0xff;
      this.bytes[at + MAP.high] = r.high & 0xff;
    }
  }

  clone() { return new FxRecord(this.bytes, this.kind); }

  /** A description a human can read, and a diff can show. */
  describe(units) {
    const out = { kind: this.kind, name: this.name, stages: {}, map: [] };
    for (const stage of this.stageNames) {
      const id = this.device(stage);
      const unit = unitFor(units, stage === "mfx" ? "mfx" : "ifx", id);
      out.stages[stage] = {
        device: id,
        unit: unit ? unit.unit : id === 0 ? null : "unknown",
        params: this.params(units, stage).map(p => ({ name: p.name, value: p.value })),
      };
    }
    out.map = this.map;
    return out;
  }
}
