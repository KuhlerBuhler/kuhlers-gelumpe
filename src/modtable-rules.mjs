/**
 * What the page checks in an edited modulation type before the copy goes to the emulator check. Same severities as
 * the effect rules in rules.mjs. Every rule is a warning: all of it was measured in the emulator, as engine values and
 * words to the DSP, none of it heard on a device (data/findings.mjs, modType.*; measure:2026-10-15/modulation-stufe2).
 *
 * A rule only speaks about what differs from `was`, the entry as the file has it, so a file's own odd values
 * do not drown the ones a person set. Without `was` every value counts.
 */
import { SLOT_COUNT } from "./modtable.mjs";

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
 * @returns {Array<{severity: "warn", code: string, where: string, message: string}>}
 */
export function lintModType(now, was) {
  const findings = [];
  const warn = (code, where, message) => findings.push({ severity: "warn", code, where, message });

  if ((!was || now.curve !== was.curve) && (now.curve < CURVE_MEASURED[0] || now.curve > CURVE_MEASURED[1])) {
    warn("mod-curve-unmeasured", "Kurve",
      now.curve === 7
        ? "Kurve 7 lief im Emulator wie Kurve 4 (Zufall). Gemessen sind 0 bis 6, gehört wurde keine."
        : `Kurve ${now.curve} liegt hinter den sieben gemessenen Wellenformen (0 bis 6): die Firmware liest dort hinter eine Tabelle von acht Einträgen, im Emulator kam der Sägezahn oder Sample and Hold heraus. Gehört wurde nichts.`);
  }

  for (let k = 0; k < SLOT_COUNT; k++) {
    const s = now.slots[k];
    const old = was?.slots[k];
    const at = `Slot ${k + 1}`;
    const changed = key => !old || !same(s[key], old[key]);
    if (changed("target") && TARGETS_UNCLEAR.includes(s.target)) {
      warn("mod-target-unclear", at,
        `${at}: Ziel-Code ${s.target} wirkt im Emulator (Engine-Wert und Pakete zum DSP ändern sich), keine der 72 Arten nutzt ihn. Was er am Klang ändert, ist nicht gemessen.`);
    }
    if (["source", "target", "lo", "hi"].some(changed) && s.target !== 0 && !slotActive(s)) {
      warn("mod-slot-silent", at,
        `${at} hat ein Ziel, tut im Emulator aber nichts: ${s.source > 1 ? "die Quelle ist aus" : "die Stärke ist 0 (von und bis stehen auf 0)"}.`);
    }
    if ((changed("lo") || changed("hi")) && s.lo < 0 && s.hi > 0) {
      warn("mod-strength-lo-ignored", at,
        `${at}: bei "von" unter 0 und "bis" über 0 lief die Stärke im Emulator immer von 0 bis 63, der Wert bei "von" zählte nicht.`);
    }
  }

  const changedSlots = now.slots.map((s, k) => !was || Object.keys(s).some(key => !same(s[key], was.slots[k][key])));
  const targets = new Map();
  now.slots.forEach((s, k) => { if (slotActive(s)) targets.set(s.target, [...(targets.get(s.target) ?? []), k]); });
  for (const [target, ks] of targets) {
    if (ks.length > 1 && ks.some(k => changedSlots[k])) {
      warn("mod-slots-add", `Slot ${ks.map(k => k + 1).join(", ")}`,
        `Die Slots ${ks.map(k => k + 1).join(" und ")} zielen auf dasselbe Ziel (Code ${target}) und addieren sich: bei Pitch lief die Spitze im Emulator auf das Doppelte.`);
    }
  }

  if (was && now.curve !== was.curve && !now.slots.some(s => slotActive(s) && s.source === 1)) {
    warn("mod-curve-unused", "Kurve",
      "Die Kurve ist die Wellenform der LFO-Einheit und wirkte im Emulator nur bei Slots mit der Quelle LFO. Kein Slot dieser Art hat sie.");
  }
  return findings;
}

/** All 72 entries; every finding carries the index of its type. */
export function lintModTypes(types, original) {
  return types.flatMap((t, i) => lintModType(t, original?.[i]).map(f => ({ ...f, type: i })));
}
