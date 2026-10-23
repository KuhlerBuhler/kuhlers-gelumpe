/**
 * Checks against the user's own factory data, one per `factory-check:<name>`
 * evidence in the device map and the findings.
 *
 * They need real files and run only in `npm run test:local`:
 *   E2_VSB       a SYSTEM.VSB with Hacktribe (factory slots: mfx 1-32, ifx 1-49)
 *   E2_PATTERNS  a pattern backup, ideally the factory bank
 *
 * Each check throws with a message when the claim does not hold, and returns
 * a short line of what it saw.
 */
import { FACTORY_SLOTS } from "../src/profile.mjs";
import { field, offsetOf, TABLES } from "../src/map/index.mjs";
import { tableEntry, patternInBackup, PATTERN_FILE } from "../src/map/address.mjs";
import { locateModTable } from "../src/modtable.mjs";
import FINDINGS from "../data/findings.mjs";
import FX_RANGES from "../data/map/fx-ranges.mjs";
import { GAIN_STAGING, REC, STAGE_BLOCK_SIZE } from "../src/layout.mjs";

// Addresses come from the map, so a wrong map entry fails the check that is its evidence.
const at = (tableId, index, fieldId, indices = []) => tableEntry(tableId, index).file + offsetOf(field(fieldId), indices);
const text = (bytes, from, n) => String.fromCharCode(...bytes.subarray(from, from + n));

const factory = (image, kind) => image.list(kind).filter(e => e.slot <= FACTORY_SLOTS[kind]);

function assert(ok, message) {
  if (!ok) throw new Error(message);
}

export const VSB_CHECKS = {
  "fx-params-max-127"({ image, units }) {
    let max = 0;
    for (const kind of ["mfx", "ifx"]) {
      for (const { record } of factory(image, kind)) {
        for (const stage of record.stageNames) {
          for (const p of record.params(units, stage)) max = Math.max(max, p.value);
        }
      }
    }
    assert(max <= 127, `a factory parameter holds ${max}`);
    return `highest factory parameter value ${max}`;
  },

  "gain-staging"({ image, units }) {
    const seen = [];
    for (const u of GAIN_STAGING.unplayable) {
      const values = [];
      for (const { record } of factory(image, "ifx")) {
        for (const stage of record.stageNames) {
          if (record.device(stage) !== u.unit) continue;
          values.push(record.params(units, stage).find(p => p.name === u.param).value);
        }
      }
      assert(values.length > 0, `no factory preset runs unit 0x${u.unit.toString(16)}`);
      assert(Math.max(...values) < u.value, `a factory preset holds ${u.param} ${Math.max(...values)}, the heard unplayable value is ${u.value}`);
      seen.push(`0x${u.unit.toString(16)} ${u.param} ${Math.min(...values)} to ${Math.max(...values)} over ${values.length} presets, unplayable from ${u.value}`);
    }
    return seen.join("; ");
  },

  "fx-param-ranges"({ image, units }) {
    let checked = 0;
    const over = [];
    for (const kind of ["mfx", "ifx"]) {
      for (const { slot, name, record } of factory(image, kind)) {
        for (const stage of record.stageNames) {
          const table = FX_RANGES.units[`0x${record.device(stage).toString(16).padStart(2, "0")}`];
          if (!table) continue;
          for (const p of record.params(units, stage)) {
            const [min, max] = table[p.index];
            const top = min < 0 ? max - min : max;
            if (top === 0) continue;
            checked++;
            if (p.value > top) over.push(`${kind} ${slot} ${name}: ${p.name} ${p.value} > ${top}`);
          }
        }
      }
    }
    assert(checked > 500, `only ${checked} factory parameters had a table range`);
    assert(over.length <= checked / 100, `${over.length} of ${checked} factory values above the table range: ${over.join("; ")}`);
    return `${checked - over.length} of ${checked} factory values within the table range, ${over.length} above${over.length ? ` (${over.join("; ")})` : ""}`;
  },

  "fx-filter-output"({ image, units }) {
    const want = [[/^(LP|Low Pass)/, 2, "LPF2"], [/^(BP|Band)/, 3, "BPF"], [/^(HP|High Pass)/, 4, "HPF"]];
    const seen = [];
    for (const { slot, name, record } of factory(image, "ifx")) {
      for (const stage of record.stageNames) {
        if (record.device(stage) !== 0x0a) continue;
        const value = record.params(units, stage).find(p => p.name === "output_select").value;
        const hit = want.find(([re]) => re.test(name));
        if (!hit) continue;
        assert(value === hit[1], `IFX ${slot} ${name} holds ${value}, expected ${hit[1]} (${hit[2]})`);
        seen.push(`${name}=${hit[2]}`);
      }
    }
    assert(seen.length >= 6, `only ${seen.length} factory filter presets matched by name`);
    return `factory filter presets agree with the output names: ${seen.join(", ")}`;
  },

  "insert-master-field"({ image }) {
    const seen = new Map();
    for (const { record } of factory(image, "ifx")) {
      const v = record.device("mfx");
      seen.set(v, (seen.get(v) || 0) + 1);
    }
    assert([...seen.keys()].every(v => v === 0 || v === 0x27), `insert presets carry ${[...seen.keys()]} in the master field`);
    return `master field in insert presets: ${[...seen].map(([k, n]) => `0x${k.toString(16)} x${n}`).join(", ")}`;
  },

  "stage-block-shared"({ image }) {
    const seen = [];
    for (const kind of ["mfx", "ifx"]) {
      const records = factory(image, kind).map(e => e.record);
      for (const stage of records[0].stageNames) {
        const { device: at, params } = REC.stage[stage];
        const blocks = new Set();
        let filled = 0;
        for (const record of records) {
          if (!record.device(stage)) continue;
          filled++;
          const rest = record.bytes.slice(at, at + STAGE_BLOCK_SIZE);
          rest[0] = rest[1] = 0;
          for (let i = params - at; i < rest.length; i += 2) rest[i] = 0;
          blocks.add(rest.join(","));
        }
        assert(filled > 0, `no factory ${kind} preset fills ${stage}`);
        assert(blocks.size === 1, `the ${stage} blocks of the factory ${kind} presets differ beyond the device, the byte after it and the parameters: ${blocks.size} kinds`);
        seen.push(`${stage} ${filled}`);
      }
    }
    return `one stage block per position apart from device, the byte after it and the parameters: ${seen.join(", ")}`;
  },

  "stage2-factory-chains"({ image }) {
    const chains = new Set();
    for (const { record } of factory(image, "ifx")) {
      const second = record.device("ifx2");
      if (second) chains.add(`${record.device("ifx1").toString(16)}->${second.toString(16)}`);
    }
    const allowed = new Set(FINDINGS.find(f => f.id === "factoryChains").chains.map(([a, b]) => `${a.toString(16)}->${b.toString(16)}`));
    assert([...chains].every(c => allowed.has(c)), `factory chains: ${[...chains]}`);
    return `factory two-stage chains: ${[...chains].join(", ")}`;
  },

  "ifx-no-y"({ image }) {
    for (const { slot, record } of factory(image, "ifx")) {
      for (const row of record.map) {
        assert(![0x43, 0x46, 0x47].includes(row.source), `IFX ${slot} drives a row from Y (${row.source.toString(16)})`);
      }
    }
    return "no factory insert preset uses a Y source";
  },

  "mfx-fade-shapes"({ image }) {
    let switchFade = 0, inputFade = 0, mute = 0, hacktribe = 0;
    const none = [];
    for (const { slot, record } of factory(image, "mfx")) {
      if (record.device("mfx") === 0x27) { mute++; continue; }
      const sw = record.map.some(r => r.source === 0x41 && r.chain === 0x0a);
      const inp = record.map.some(r => r.chain === 0x07 && r.low === 0);
      // Hacktribe's file moves Big Hall's 0x41 row to chain 2, so it has no fade there; Korg's own 2.02 has one.
      if (sw) switchFade++;
      else if (inp) inputFade++;
      else if (slot === 10 && record.name.trim() === "Big Hall" && record.map.some(r => r.source === 0x41 && r.chain === 2)) hacktribe++;
      else none.push(`${slot} ${record.name.trim()}`);
    }
    assert(none.length === 0, `factory master presets without a fade: ${none.join(", ")}`);
    return `switch fade ${switchFade}, input fade ${inputFade}, mute unit ${mute}${hacktribe ? ", Hacktribe's Big Hall without one" : ""}`;
  },

  "level-mod-play-row"({ image, units }) {
    let n = 0;
    for (const kind of ["mfx", "ifx"]) {
      for (const { slot, record } of factory(image, kind)) {
        for (const [i, stage] of record.stageNames.entries()) {
          if (record.device(stage) !== 0x15) continue;
          const p = record.params(units, stage).find(x => x.name === "lfo_reset");
          const chain = kind === "mfx" ? 2 : i;
          assert(record.map.some(r => r.source === 0x4a && r.chain === chain && r.param === p.index),
            `${kind} ${slot} runs level_mod without a play row`);
          n++;
        }
      }
    }
    assert(n > 0, "no factory preset uses level_mod");
    return `${n} factory presets with level_mod, all with a play row`;
  },

  "ifx-menu-sites-agree"({ image }) {
    const c = image.ifxCount;
    assert(c.agreed, `insert menu sites disagree: ${c.counts} / ${c.last}`);
    return `insert menu length ${c.value}, all 13 sites agree`;
  },

  "init-pattern-ptst"({ image }) {
    const tag = text(image.bytes, at("table.initPattern", 0, "pattern.magic"), 4);
    assert(tag === "PTST", `init pattern starts with ${tag}`);
    return "init pattern starts with PTST";
  },

  "groove-records"({ image }) {
    const head = text(image.bytes, at("table.groove", 0, "groove.magic"), 4);
    const tail = text(image.bytes, at("table.groove", 0, "groove.endMagic"), 4);
    assert(head === "GVST" && tail === "GVED", `groove slot 0 reads ${head}/${tail}`);
    return "groove slot 0 framed GVST/GVED";
  },

  "mod-table-targets"({ image }) {
    const pattern = [3, 1, 2, 4, 0, 5];
    for (let i = 0; i < TABLES.get("table.modType").count; i++) {
      const v = image.bytes[at("table.modType", i, "modType.target")];
      assert(v === pattern[i % 6], `modulation type ${i} targets ${v}`);
    }
    return "all 72 modulation types follow 03 01 02 04 00 05";
  },

  "mod-table-read-copy"({ image }) {
    const found = locateModTable(image.bytes);
    assert(found.ok, found.reasons?.join(" "));
    const mapped = TABLES.get("table.modType").file;
    assert(found.file === mapped, `the code reads the table at 0x${found.file.toString(16)}, the map says 0x${mapped.toString(16)}`);
    const stock = TABLES.get("table.modTypeStock");
    const { count, stride } = TABLES.get("table.modType");
    let differing = 0;
    for (let i = 4; i < count * stride; i++) if (image.bytes[mapped + i] !== image.bytes[stock.file + i]) differing++;
    assert(differing === 0, `${differing} bytes differ between the copy that is read and Korg's copy`);
    return `the table readers point at 0x${found.file.toString(16)} (${found.readers.length} words), Korg's copy is equal behind its first 4 bytes`;
  },

  "mfx-count-ram"({ image }) {
    const n = image.bytes[field("menu.mfxCount").where.offset];
    assert(n >= 32 && n <= 100, `master menu length reads ${n}`);
    return `master menu length ${n}`;
  },
};

const blocks = bytes => {
  const out = [];
  for (let n = 0; n < PATTERN_FILE.count && patternInBackup(n) + 0x4000 <= bytes.length; n++) {
    out.push(bytes.subarray(patternInBackup(n), patternInBackup(n) + 0x4000));
  }
  return out;
};
const SIGNED = ["part.egInt", "part.pan", "part.pitch"].map(field);

export const PATTERN_CHECKS = {
  "pattern-frames"({ bytes }) {
    const all = blocks(bytes);
    for (const [i, b] of all.entries()) {
      const head = String.fromCharCode(...b.subarray(0, 4));
      const tail = String.fromCharCode(...b.subarray(15356, 15360));
      assert(head === "PTST" && tail === "PTED", `pattern ${i + 1} framed ${head}/${tail}`);
    }
    return `${all.length} patterns framed PTST/PTED`;
  },

  "pattern-signed-bytes"({ bytes }) {
    let negatives = 0;
    for (const b of blocks(bytes)) for (let p = 0; p < 16; p++) for (const f of SIGNED) if (b[offsetOf(f, [p])] > 127) negatives++;
    assert(negatives > 0, "no byte above 127 in parts 15, 25, 36");
    return `${negatives} negative values in part bytes 15, 25, 36`;
  },

  "pattern-step-reserved"({ bytes }) {
    let active = 0;
    const on = field("step.on");
    for (const b of blocks(bytes)) for (let p = 0; p < 16; p++) for (let s = 0; s < 64; s++) {
      const from = offsetOf(on, [p, s]);
      const st = b.subarray(from, from + 12);
      if (!st[0]) continue;
      active++;
      assert(st[8] === 0 && st[9] === 0 && st[10] === 0 && st[11] === 0, "a step has data in bytes 8 to 11");
    }
    return `${active} active steps, bytes 8 to 11 all zero`;
  },

  "pattern-mfx-reserved"({ bytes }) {
    // Byte 64 sits between pad Y and hold and carries no field of its own.
    const between = offsetOf(field("pattern.mfx.padY")) + 1;
    const seen = new Set(blocks(bytes).map(b => b[between]));
    assert(seen.size === 1 && seen.has(1), `pattern byte 64 holds ${[...seen]}`);
    return "pattern byte 64 is 1 everywhere";
  },
};
