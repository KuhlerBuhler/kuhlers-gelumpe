/**
 * Everything that has ever gone wrong, written down so it cannot go wrong
 * twice.
 *
 * Each rule is something that was paid for once: a device that had to be
 * restarted, an evening spent on a preset that turned out to be silent, or a
 * parameter that sounded broken because a single byte sat outside the range
 * Korg uses everywhere else. None of it is guesswork about what the hardware
 * might dislike.
 *
 * Severities:
 *   fatal   the device stops making sound or hangs, a restart is needed
 *   silent  the preset loads and plays nothing
 *   error   structurally wrong; a control will not do what it says
 *   warn    legal, but outside everything the factory presets ever do
 *   note    cosmetic
 */
import {
  REC, SOURCES, CHAINS, STAGE2, STAGE1_NEEDS_SOLO, MFX_DEVICE_RANGE,
  MFX_MUTE, ENUM_PARAMS, LOUDNESS, OFF_AT, PLAY_ROW_RESYNCS,
} from "./layout.mjs";
import { unitFor, hex } from "./units.mjs";
import { profileKey } from "./profile.mjs";
import { judgeOutput } from "./gain.mjs";
import { finding } from "./finding.mjs";
import { text } from "./text.mjs";

export const SEVERITY_ORDER = ["fatal", "silent", "error", "warn", "note"];

/** The parameter that makes a unit inaudible, and where its off position is. */
const OFF_PARAMS = Object.keys(OFF_AT);

/** Sources whose zero position is the bottom of the control's travel. */
const BOTTOM_SOURCES = new Set([0x42, 0x45]);

export function lint(record, { units, profile = null } = {}) {
  const findings = [];
  const add = (severity, code, where, key, vars) => findings.push(finding({ severity, code, where }, key, vars));

  checkName(record, add);
  checkFiledCorrectly(record, add);
  const stages = checkStages(record, units, add);
  checkMap(record, units, stages, add);
  checkFxOnCrossfade(record, add);
  checkZeroIsOff(record, units, stages, add);
  checkLoudness(record, units, stages, profile, add);
  checkEnums(record, units, stages, profile, add);
  checkPlayRow(record, units, stages, add);
  if (profile) checkAgainstFactory(record, units, stages, profile, add);

  findings.sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));
  return findings;
}

function checkName(record, add) {
  const name = record.name;
  if (!name) add("note", "name-empty", "name", "lint.name.empty");
  for (const ch of name) {
    if (ch.charCodeAt(0) < 0x20 || ch.charCodeAt(0) > 0x7e) {
      add("note", "name-unprintable", "name", "lint.name.unprintable", { char: JSON.stringify(ch) });
      break;
    }
  }
}

/**
 * Both tables hold the same 524 bytes, so a record copied out of the wrong
 * one looks perfectly valid and plays nothing. What tells them apart is which
 * device field is filled: a master preset has the master field set and both
 * insert stages at zero, an insert preset has stage one set and the master
 * field at the mute unit or zero.
 */
function checkFiledCorrectly(record, add) {
  const master = record.bytes[REC.stage.mfx.device];
  const first = record.bytes[REC.stage.ifx1.device];

  if (record.kind === "mfx" && !master && first) {
    add("silent", "wrong-table", "record", "lint.wrongTable.master", { unit: hex(first) });
  }
  if (record.kind === "ifx" && !first && master && master !== MFX_MUTE) {
    add("silent", "wrong-table", "record", "lint.wrongTable.insert", { unit: hex(master) });
  }
  if (record.kind === "ifx" && master && master !== MFX_MUTE) {
    add("warn", "insert-master-field", "record", "lint.insertMasterField", { unit: hex(master), mute: hex(MFX_MUTE) });
  }
}

/** @returns {Map<string, {device:number, unit:object|null}>} the stages in use */
function checkStages(record, units, add) {
  const stages = new Map();

  for (const stage of record.stageNames) {
    const device = record.device(stage);
    if (!device) continue;
    const kind = stage === "mfx" ? "mfx" : "ifx";
    const unit = unitFor(units, kind, device);
    stages.set(stage, { device, unit });

    if (!unit) {
      add("warn", "device-unknown", stage, "lint.deviceUnknown", { stage, unit: hex(device) });
    }

    if (record.kind === "ifx" && device >= MFX_DEVICE_RANGE[0] && device <= MFX_DEVICE_RANGE[1]) {
      add("fatal", "master-unit-in-insert", stage, "lint.masterUnitInInsert", { stage, unit: hex(device) });
    }
  }

  if (record.kind === "mfx") {
    // A master slot runs exactly one unit. The insert fields exist in the
    // record but Korg leaves them at zero in all of its master presets.
    for (const stage of ["ifx1", "ifx2"]) {
      if (record.device(stage)) {
        add("error", "master-extra-stage", stage, "lint.masterExtraStage", { unit: hex(record.device(stage)), stage });
      }
    }
    return stages;
  }

  const second = record.device("ifx2");
  if (second) {
    const known = STAGE2[second];
    if (!known) {
      add("warn", "stage2-untested", "ifx2", "lint.stage2.untested", {
        unit: hex(second), proven: Object.entries(STAGE2).filter(([, v]) => v.verdict === "ok").map(([k]) => hex(Number(k))).join(", "),
      });
    } else if (known.verdict === "fatal") {
      add("fatal", "stage2-fatal", "ifx2", "lint.stage2.known", { unit: hex(second), note: known.note });
    } else if (known.verdict === "silent") {
      add("silent", "stage2-silent", "ifx2", "lint.stage2.known", { unit: hex(second), note: known.note });
    }

    const solo = STAGE1_NEEDS_SOLO[record.device("ifx1")];
    if (solo) {
      add(solo.verdict || "fatal", "stage1-needs-solo", "ifx1", "lint.stage1NeedsSolo", { unit: hex(record.device("ifx1")), note: solo.note });
    }
  }

  return stages;
}

function checkMap(record, units, stages, add) {
  const seen = new Set();

  for (const row of record.map) {
    const where = `map ${row.index}`;
    const source = SOURCES[row.source];

    if (!source) {
      add("error", "map-source-unknown", where, "lint.map.sourceUnknown", { source: hex(row.source) });
    } else if (record.kind === "ifx" && !source.ifx) {
      add("error", "map-source-unavailable", where, "lint.map.sourceUnavailable", { name: source.name });
    }

    const chain = CHAINS[row.chain];
    if (!chain) {
      add("error", "map-chain-unknown", where, "lint.map.chainUnknown", { chain: hex(row.chain) });
      continue;
    }

    if (chain.stage) {
      const expected = record.kind === "mfx" ? ["mfx"] : ["ifx1", "ifx2"];
      if (!expected.includes(chain.stage)) {
        add("error", "map-chain-wrong-kind", where, "lint.map.chainWrongKind", { name: chain.name, kind: record.kind });
        continue;
      }
      const target = stages.get(chain.stage);
      if (!target) {
        add("error", "map-chain-empty", where, "lint.map.chainEmpty", { name: chain.name });
        continue;
      }
      if (target.unit && row.param >= target.unit.params.length) {
        add("error", "map-param-out-of-range", where, "lint.map.paramOutOfRange", { param: row.param, unit: target.unit.unit, count: target.unit.params.length });
      }
    }

    const key = `${row.source}:${row.chain}:${row.param}`;
    if (seen.has(key)) {
      add("note", "map-duplicate", where, "lint.map.duplicate");
    }
    seen.add(key);

    if (row.low === row.high) {
      add("note", "map-flat", where, "lint.map.flat", { value: row.low });
    }
  }
}

/**
 * A master preset needs something that makes it inaudible while the effect is
 * switched off. Leave it out and no sound comes out at all unless the
 * touchpad is being held, which took a long time to understand the first time.
 *
 * There are three shapes across the 32 factory master presets: a cross-fade
 * of the output stage driven by the switch, a fade of the input stage from
 * zero, and, in four of them, nothing at all because they run the mute unit
 * and have no effect to fade.
 *
 * An earlier write-up claimed every preset carries the output pair. It does
 * not, and a check built on that claim flags half the factory bank.
 *
 * The input fade does not have to come from the switch. A touchpad axis works
 * too, because an axis reads zero until it is touched. That is how the Short
 * Delay built here does it, and it is why this check looks at where the row
 * starts rather than at what drives it.
 *
 * Insert presets do not have this and must not be given it.
 */
function checkFxOnCrossfade(record, add) {
  if (record.kind !== "mfx") return;
  if (record.device("mfx") === MFX_MUTE) return;   // nothing to fade

  const fade = record.map.some(r =>
    (r.chain === 0x07 && r.low === 0) ||            // input opens up from nothing
    (r.source === 0x41 && r.chain === 0x0a));       // switch cross-fades the output
  if (fade) return;

  add("silent", "no-switch-on-fade", "map", "lint.noSwitchOnFade");
}

/**
 * What the hearing tests settled on, as opposed to what the bytes allow. An
 * output level of 124 is not a bold choice, it is unplayable, and delay
 * feedback above 90 stacks until there is nothing left to hear. The output
 * levels are judged in gain.mjs, where the page reads the same verdict.
 */
function checkLoudness(record, units, stages, profile, add) {
  for (const [stage, info] of stages) {
    if (!info.unit) continue;
    for (const p of info.unit.params) {
      const value = record.paramAt(stage, p.index);
      const verdict = judgeOutput(info.device, p.name, value, profile?.params[profileKey(record.kind, info.device, p.name)]);
      if (verdict) add("warn", verdict.code, stage, "lint.output", { unit: info.unit.unit, param: p.name, value, verdict: verdict.text });
      if (/^(fb_depth|feedback)$/.test(p.name) && value > LOUDNESS.feedbackCeiling) {
        add("warn", "feedback-runs-away", stage, "lint.feedbackRunsAway", { unit: info.unit.unit, param: p.name, value, ceiling: LOUDNESS.feedbackCeiling });
      }
    }
  }
}

/**
 * Fields that pick from a list rather than sweep a range. What the numbers
 * mean is written down nowhere, and an invented one has taken the device's
 * output down until a restart.
 */
function checkEnums(record, units, stages, profile, add) {
  for (const [stage, info] of stages) {
    if (!info.unit) continue;
    for (const p of info.unit.params) {
      const known = ENUM_PARAMS[p.name];
      if (!known) continue;
      const value = record.paramAt(stage, p.index);

      if (!profile) {
        add("note", "enum-unchecked", stage, "lint.enumUnchecked", { unit: info.unit.unit, param: p.name });
      }
    }
  }
}

/**
 * A modulator with no play row free-runs and comes in at a different point
 * after every stop and play. Heard on two presets alike but for the row.
 * Every factory preset using this unit carries it.
 */
function checkPlayRow(record, units, stages, add) {
  for (const [stage, info] of stages) {
    if (!info.unit || !PLAY_ROW_RESYNCS.units.includes(info.device)) continue;
    const reset = info.unit.params.find(x => x.name === "lfo_reset");
    if (!reset) continue;

    const chainForStage = Number(Object.entries(CHAINS).find(([, c]) => c.stage === stage)[0]);
    const onPlay = record.map.some(r =>
      r.source === 0x4a && r.chain === chainForStage && r.param === reset.index);
    if (onPlay) continue;

    add("warn", "no-play-row", stage, "lint.noPlayRow", { unit: info.unit.unit });
  }
}

/**
 * Rule one from the hearing tests: with the control at rest the effect has to
 * be gone. A preset that only moves a tone parameter is always on, and the
 * control merely changes its colour. Three presets shipped that way before
 * anyone noticed.
 */
function checkZeroIsOff(record, units, stages, add) {
  const rows = record.map.filter(r => BOTTOM_SOURCES.has(r.source));
  if (!rows.length) return;

  for (const [stage, info] of stages) {
    if (!info.unit) continue;
    const off = info.unit.params.find(p => OFF_PARAMS.includes(p.name));
    if (!off) continue;
    const offValue = OFF_AT[off.name];
    if (offValue === null) continue;   // nobody has worked out where off is

    const chainForStage = Number(
      Object.entries(CHAINS).find(([, c]) => c.stage === stage)[0]
    );
    const forStage = rows.filter(r => r.chain === chainForStage);
    // If the control never touches this stage there is nothing to say: the
    // stage is simply part of the preset's fixed sound.
    if (!forStage.length) continue;

    const driven = forStage.find(r => r.param === off.index);

    const bipolar = offValue !== 0 ? text("lint.bipolar", { off: offValue }) : "";

    if (driven) {
      if (driven.low !== offValue) {
        add("warn", "rest-not-silent", stage, "lint.restNotSilent.driven", { unit: info.unit.unit, param: off.name, low: driven.low, off: offValue, bipolar });
      }
      continue;
    }

    if (record.paramAt(stage, off.index) !== offValue) {
      add("warn", "rest-not-silent", stage, "lint.restNotSilent.fixed", { unit: info.unit.unit, param: off.name, value: record.paramAt(stage, off.index), bipolar });
    }
  }
}

/**
 * Hold every value against what Korg does with the same unit. This is the
 * check that would have caught an output gain of 95 where the factory never
 * leaves 32 to 36, and a bit depth sitting at its most destructive setting
 * before the control is even touched.
 */
function checkAgainstFactory(record, units, stages, profile, add) {
  for (const [stage, info] of stages) {
    if (!info.unit) continue;
    for (const p of info.unit.params) {
      const stat = profile.params[profileKey(record.kind, info.device, p.name)];
      if (!stat) continue;
      const value = record.paramAt(stage, p.index);

      if (stat.enum && !stat.enum.includes(value)) {
        add("error", "value-not-in-factory-set", stage, "lint.valueNotInFactorySet", { unit: info.unit.unit, param: p.name, value, values: stat.enum.join(", "), samples: stat.samples });
        continue;
      }

      // A range learned from a single preset says nothing at all. Three is
      // still thin, so the sample count travels with the message and the
      // reader decides how much it is worth.
      // A parameter that never moved across the factory presets only says
      // something once enough presets have declined to move it.
      const constant = stat.min === stat.max;
      const enough = constant ? stat.samples >= 6 : stat.samples >= 3;
      if (!stat.enum && enough && (value < stat.min || value > stat.max)) {
        add("warn", "value-outside-factory-range", stage, "lint.valueOutsideFactoryRange", { unit: info.unit.unit, param: p.name, value, samples: stat.samples, min: stat.min, max: stat.max });
      }
    }
  }
}

export const worst = findings =>
  findings.length
    ? SEVERITY_ORDER.find(s => findings.some(f => f.severity === s))
    : null;
