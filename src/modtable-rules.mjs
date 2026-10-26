/**
 * What the page checks in an edited modulation type before the copy goes to the emulator check. Same severities as
 * the effect rules in rules.mjs. Every rule is a warning: all of it was measured in the emulator, as engine values and
 * words to the DSP, none of it heard on a device (data/findings.mjs, modType.*; measure:2026-10-15/modulation-stufe2).
 *
 * A rule only speaks about what differs from `was`, the entry as the file has it, so a file's own odd values
 * do not drown the ones a person set. Without `was` every value counts.
 */
import { SLOT_COUNT } from "./modtable.mjs";
import { finding } from "./finding.mjs";
import { render, text } from "./text.mjs";

/** The waveforms measured: 0 to 6. 7 acts as 4, from 8 on the firmware reads past an eight byte table. */
export const CURVE_MEASURED = [0, 6];

/** Target codes with a measured effect on a value of the engine and a word to the DSP; 4 to 7 act too, but what they do to the sound is open. */
export const TARGETS_KNOWN = [1, 2, 3, 8, 9, 10];
export const TARGETS_UNCLEAR = [4, 5, 6, 7];

const same = (a, b) => a === b;

/** Whether a slot does anything: a measured target, a source of the envelope or the LFO, a strength other than 0. */
export const slotActive = s => s.target !== 0 && s.source <= 1 && !(s.lo === 0 && s.hi === 0);

/**
 * @param {ReturnType<import("./modtable.mjs").readModType>} now
 * @param {ReturnType<import("./modtable.mjs").readModType>} [was]
 * @returns {Array<{severity: "warn", code: string, where: string, message: string, text: object}>} `text` is the message as a text (src/text.mjs)
 */
export function lintModType(now, was) {
  const findings = [];
  const warn = (code, where, key, vars) => findings.push(finding({ severity: "warn", code, where: render(where) }, key, vars));

  if ((!was || now.curve !== was.curve) && (now.curve < CURVE_MEASURED[0] || now.curve > CURVE_MEASURED[1])) {
    if (now.curve === 7) warn("mod-curve-unmeasured", text("lint.mod.curve"), "lint.mod.curve7");
    else warn("mod-curve-unmeasured", text("lint.mod.curve"), "lint.mod.curveBeyond", { curve: now.curve });
  }

  for (let k = 0; k < SLOT_COUNT; k++) {
    const s = now.slots[k];
    const old = was?.slots[k];
    const at = text("lint.mod.slot", { slot: k + 1 });
    const changed = key => !old || !same(s[key], old[key]);
    if (changed("target") && TARGETS_UNCLEAR.includes(s.target)) {
      warn("mod-target-unclear", at, "lint.mod.targetUnclear", { at, target: s.target });
    }
    if (["source", "target", "lo", "hi"].some(changed) && s.target !== 0 && !slotActive(s)) {
      warn("mod-slot-silent", at, "lint.mod.slotSilent", { at, why: text(s.source > 1 ? "lint.mod.slotSilent.source" : "lint.mod.slotSilent.strength") });
    }
    if ((changed("lo") || changed("hi")) && s.lo < 0 && s.hi > 0) {
      warn("mod-strength-lo-ignored", at, "lint.mod.loIgnored", { at });
    }
  }

  const changedSlots = now.slots.map((s, k) => !was || Object.keys(s).some(key => !same(s[key], was.slots[k][key])));
  const targets = new Map();
  now.slots.forEach((s, k) => { if (slotActive(s)) targets.set(s.target, [...(targets.get(s.target) ?? []), k]); });
  for (const [target, ks] of targets) {
    if (ks.length > 1 && ks.some(k => changedSlots[k])) {
      warn("mod-slots-add", text("lint.mod.slot", { slot: ks.map(k => k + 1).join(", ") }), "lint.mod.slotsAdd", { slots: ks.map(k => k + 1).join(render(text("lint.mod.and"))), target });
    }
  }

  if (was && now.curve !== was.curve && !now.slots.some(s => slotActive(s) && s.source === 1)) {
    warn("mod-curve-unused", text("lint.mod.curve"), "lint.mod.curveUnused");
  }
  return findings;
}

/** All 72 entries; every finding carries the index of its type. */
export function lintModTypes(types, original) {
  return types.flatMap((t, i) => lintModType(t, original?.[i]).map(f => ({ ...f, type: i })));
}
