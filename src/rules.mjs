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

export const SEVERITY_ORDER = ["fatal", "silent", "error", "warn", "note"];

/** The parameter that makes a unit inaudible, and where its off position is. */
const OFF_PARAMS = Object.keys(OFF_AT);

/** Sources whose zero position is the bottom of the control's travel. */
const BOTTOM_SOURCES = new Set([0x42, 0x45]);

export function lint(record, { units, profile = null } = {}) {
  const findings = [];
  const add = (severity, code, message, where) => findings.push({ severity, code, message, where });

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
  if (!name) add("note", "name-empty", "the preset has no name, the device shows a blank menu entry", "name");
  for (const ch of name) {
    if (ch.charCodeAt(0) < 0x20 || ch.charCodeAt(0) > 0x7e) {
      add("note", "name-unprintable", `the name contains a character the display cannot show: ${JSON.stringify(ch)}`, "name");
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
    add("silent", "wrong-table",
      `this looks like an insert preset sitting in the master table: the master field is empty ` +
      `and insert stage 1 holds ${hex(first)}. Copied from the wrong donor, it selects and stays ` +
      `silent.`, "record");
  }
  if (record.kind === "ifx" && !first && master && master !== MFX_MUTE) {
    add("silent", "wrong-table",
      `this looks like a master preset sitting in the insert table: insert stage 1 is empty and ` +
      `the master field holds ${hex(master)}.`, "record");
  }
  if (record.kind === "ifx" && master && master !== MFX_MUTE) {
    add("warn", "insert-master-field",
      `the unused master field holds ${hex(master)}. Across the factory insert presets it is ` +
      `either ${hex(MFX_MUTE)} (mute) or zero.`, "record");
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
      add("warn", "device-unknown",
        `${stage} holds ${hex(device)}, a unit nothing is known about. Its parameter list is ` +
        `unknown, so every map entry pointing at it is a guess.`, stage);
    }

    if (record.kind === "ifx" && device >= MFX_DEVICE_RANGE[0] && device <= MFX_DEVICE_RANGE[1]) {
      add("fatal", "master-unit-in-insert",
        `${stage} holds ${hex(device)}, which is a master effect unit. A master unit inside an ` +
        `insert chain hangs the device.`, stage);
    }
  }

  if (record.kind === "mfx") {
    // A master slot runs exactly one unit. The insert fields exist in the
    // record but Korg leaves them at zero in all of its master presets.
    for (const stage of ["ifx1", "ifx2"]) {
      if (record.device(stage)) {
        add("error", "master-extra-stage",
          `a master preset carries ${hex(record.device(stage))} in ${stage}. A master slot runs ` +
          `one unit; the second is ignored at best.`, stage);
      }
    }
    return stages;
  }

  const second = record.device("ifx2");
  if (second) {
    const known = STAGE2[second];
    if (!known) {
      add("warn", "stage2-untested",
        `${hex(second)} in stage 2 has never been tried. Proven there: ` +
        `${Object.entries(STAGE2).filter(([, v]) => v.verdict === "ok").map(([k]) => hex(Number(k))).join(", ")}. ` +
        `Test it over RAM, not from a flashed image.`, "ifx2");
    } else if (known.verdict === "fatal") {
      add("fatal", "stage2-fatal", `${hex(second)} in stage 2: ${known.note}`, "ifx2");
    } else if (known.verdict === "silent") {
      add("silent", "stage2-silent", `${hex(second)} in stage 2: ${known.note}`, "ifx2");
    }

    const solo = STAGE1_NEEDS_SOLO[record.device("ifx1")];
    if (solo) {
      add(solo.verdict || "fatal", "stage1-needs-solo",
        `${hex(record.device("ifx1"))} in stage 1 with a second stage behind it: ${solo.note}`, "ifx1");
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
      add("error", "map-source-unknown",
        `source ${hex(row.source)} is not one the device sends. The row does nothing.`, where);
    } else if (record.kind === "ifx" && !source.ifx) {
      add("error", "map-source-unavailable",
        `"${source.name}" only exists on the touchpad, and the touchpad drives the master effect. ` +
        `An insert preset is played with the one knob, so this row is dead.`, where);
    }

    const chain = CHAINS[row.chain];
    if (!chain) {
      add("error", "map-chain-unknown", `chain ${hex(row.chain)} is not a known target`, where);
      continue;
    }

    if (chain.stage) {
      const expected = record.kind === "mfx" ? ["mfx"] : ["ifx1", "ifx2"];
      if (!expected.includes(chain.stage)) {
        add("error", "map-chain-wrong-kind",
          `the row points at "${chain.name}", which a ${record.kind} preset does not have`, where);
        continue;
      }
      const target = stages.get(chain.stage);
      if (!target) {
        add("error", "map-chain-empty",
          `the row points at "${chain.name}", but that stage is empty`, where);
        continue;
      }
      if (target.unit && row.param >= target.unit.params.length) {
        add("error", "map-param-out-of-range",
          `parameter ${row.param} does not exist on ${target.unit.unit}, which has ` +
          `${target.unit.params.length}. The map stores a position in the parameter list, not an ` +
          `address, so this reaches past the end of the list.`, where);
      }
    }

    const key = `${row.source}:${row.chain}:${row.param}`;
    if (seen.has(key)) {
      add("note", "map-duplicate",
        `a second row drives the same parameter from the same control; the later one wins`, where);
    }
    seen.add(key);

    if (row.low === row.high) {
      add("note", "map-flat", `start and end are both ${row.low}, so the control changes nothing`, where);
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

  add("silent", "no-switch-on-fade",
    `a master preset needs something that keeps it out of the way while it is off: either the ` +
    `switch cross-fading the output stage, or the input stage opening from zero. All 28 factory ` +
    `presets that run a unit have one. Without it no sound comes out unless the touchpad is held.`,
    "map");
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
      if (verdict) add("warn", verdict.code, `${info.unit.unit}: "${p.name}" is ${value}. ${verdict.message}`, stage);
      if (/^(fb_depth|feedback)$/.test(p.name) && value > LOUDNESS.feedbackCeiling) {
        add("warn", "feedback-runs-away",
          `${info.unit.unit}: "${p.name}" is ${value}. Above ${LOUDNESS.feedbackCeiling} the ` +
          `repeats stack up until nothing is recognisable; the factory delays sit around 70. ` +
          `Deliberate is fine, but put it on a control so it can be backed off.`, stage);
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
        add("note", "enum-unchecked",
          `${info.unit.unit}: "${p.name}" picks from a list whose meanings are unknown. Build a ` +
          `factory profile so its value can be checked.`, stage);
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

    add("warn", "no-play-row",
      `${info.unit.unit}: nothing drives "lfo_reset" from the play button, so the modulator ` +
      `free-runs and comes in at a different point after every stop and play. All four factory ` +
      `presets with this unit carry that row. Setting the parameter to 1 instead does not help; ` +
      `the row is what fires it.`, stage);
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

    const bipolar = offValue !== 0 ? ` (it is bipolar; ${offValue} is the quiet point, not 0)` : "";

    if (driven) {
      if (driven.low !== offValue) {
        add("warn", "rest-not-silent",
          `${info.unit.unit}: "${off.name}" starts at ${driven.low} rather than ${offValue}, so the ` +
          `effect is already audible before the control is touched${bipolar}`, stage);
      }
      continue;
    }

    if (record.paramAt(stage, off.index) !== offValue) {
      add("warn", "rest-not-silent",
        `${info.unit.unit}: nothing drives "${off.name}" and it sits at ` +
        `${record.paramAt(stage, off.index)}. The effect is on the whole time and the control only ` +
        `changes how it sounds. Put "${off.name}" on the control instead${bipolar}.`, stage);
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
        add("error", "value-not-in-factory-set",
          `${info.unit.unit}: "${p.name}" is ${value}; the factory presets only ever use ` +
          `${stat.enum.join(", ")} across ${stat.samples} presets. This parameter looks like a ` +
          `list of choices, and an invented choice has taken the device's output down before, ` +
          `permanently until a restart.`, stage);
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
        add("warn", "value-outside-factory-range",
          `${info.unit.unit}: "${p.name}" is ${value}; across ${stat.samples} factory presets it ` +
          `stays between ${stat.min} and ${stat.max}`, stage);
      }
    }
  }
}

export const worst = findings =>
  findings.length
    ? SEVERITY_ORDER.find(s => findings.some(f => f.severity === s))
    : null;
