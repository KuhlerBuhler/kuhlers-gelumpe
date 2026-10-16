/**
 * The gatekeeper: every planned send passes here before it reaches a device.
 *
 * Four checks, in this order, each with a reason the page can show:
 *   1. may this device and this file be written at all
 *   2. does every write land in a region the map declares, and none in a protected one
 *   3. the linter, against what the slot held before
 *   4. a dry run of the exact steps against a throwaway copy of the
 *      simulated device
 *
 * It checks form, not sound. Whether a preset sounds good, or at all, only
 * ears can tell, and the page says so next to every verdict.
 */
import { checkReadGuard } from "./guards.mjs";
import { recordOf } from "./presets.mjs";
import { describeMessage, parseReadRam, parsePatternDump } from "./protocol.mjs";
import { allowedRegions, allowedExecutes } from "./plan.mjs";
import { accessOf, refusal, UNKNOWN_COMMAND } from "./protect.mjs";
import { lint, SEVERITY_ORDER } from "./rules.mjs";
import { FxRecord } from "./record.mjs";
import { isOriginalSlot } from "./firmware.mjs";
import { FACTORY_SLOTS } from "./profile.mjs";
import { SimDevice } from "./device.mjs";
import { VsbImage } from "./image.mjs";
import { lintPattern } from "./pattern-rules.mjs";
import { lintSample } from "./sample-rules.mjs";

const BLOCKING = new Set(["fatal", "silent", "error"]);

const reason = (severity, code, message) => ({ severity, code, message });
/** The refusal text of src/protect.mjs, in the gate's words: it never reaches the simulation. */
const early = text => `${text.replace(/ Gesperrt\.$/, "")} Gesperrt, bevor die Simulation es sieht.`;

/** Edits that go over Korg's own pattern and global messages, which need no Hacktribe and no file. */
const PATTERN_EDITS = new Set(["patternSend", "patternRestore", "globalSend"]);
export { PATTERN_EDITS };

/** The edits that need no preset table of Hacktribe's, so that they are allowed on Korg's original with BLECH: the display and a sample's name and tune. */
export const STOCK_EDITS = new Set(["screenWrite", "sample"]);

/** An effect record of Korg's build is addressed by `ram`, which the editor found through the pointer arrays of the file (src/presets.mjs). */
const stockRecord = edit => edit.kind === "fxRecord" && edit.ram !== undefined;

/** The address of such a record has to be the one the file's pointer array gives for that slot, or the write goes to another preset. */
export function recordAddressCheck(edit, ctx) {
  if (!stockRecord(edit)) return [];
  const bytes = ctx.session?.image?.bytes;
  const found = bytes && recordOf(bytes, edit.table, edit.slot);
  return found?.ram === edit.ram ? [] : [reason("fatal", "record-address", `Der Platz ${edit.slot} liegt laut Zeigerfeld der Firmware-Datei nicht bei 0x${(edit.ram >>> 0).toString(16)}. Gesperrt.`)];
}

/** Check 1: the things that make a device read-only. */
export function preconditions(ctx, edit = {}) {
  const out = [];
  const pattern = PATTERN_EDITS.has(edit.kind);
  if (!ctx.device) out.push(reason("error", "no-device", "Kein Gerät verbunden."));
  else {
    if (!ctx.device.versionKnown) out.push(reason("error", "unknown-device", `Unbekannter Gerätestand (Gerätesuche meldet ${ctx.device.version.join(".")}). Unbekannt heißt: nur lesen.`));
    const ram = ctx.device.ram ?? (ctx.device.hacktribe ? "hacktribe" : null);
    if (!pattern && !ram) out.push(reason("error", "no-hacktribe", "Das Gerät beantwortet weder BLECHs noch Hacktribes Befehle für das RAM. Live ins RAM geht nur mit BLECH oder Hacktribe."));
    if (edit.kind === "exec" && !ctx.device.hacktribe) out.push(reason("error", "exec-needs-hacktribe", "Code ausführen geht nur mit Hacktribes Befehl 0x57. BLECHs Befehle lesen und schreiben das RAM und führen nichts aus."));
  }
  if (!pattern) {
    if (!ctx.firmware) out.push(reason("error", "no-firmware", "Live ins RAM geht nur mit geladener Firmware-Datei: ohne sie fehlt der Simulation das Abbild und dem Prüfer das Werksprofil."));
    else if (!ctx.firmware.known && !(ctx.device?.build === "stock" && ctx.firmware.build === "stock" && (STOCK_EDITS.has(edit.kind) || stockRecord(edit)))) out.push(reason("error", "unknown-firmware", `Die Firmware-Datei ist nicht die vermessene: ${ctx.firmware.reasons.join(" ")}`));
  }
  if (ctx.blocked) out.push(reason("error", "target-blocked", ctx.blocked));
  if (edit.kind === "exec" && !ctx.rehearsed) {
    out.push(reason("fatal", "exec-needs-emulator", "Code ausführen geht nur über den Emulator: erst läuft er dort, und nur was dort bestanden hat, geht ans Gerät."));
  }
  return out;
}

/**
 * A pattern send replaces whatever is unsaved in the device's buffer. The
 * buffer has to be fetched and kept first (this cost pattern 1 once).
 */
export function backupFirst(edit, steps) {
  if (edit.kind !== "patternSend") return [];
  const firstWrite = steps.findIndex(s => s.role === "write");
  const backup = steps.findIndex(s => s.role === "backup" && s.expect.kind === "pattern");
  if (backup === -1 || backup > firstWrite) {
    return [reason("fatal", "no-pattern-backup", "Der Pattern-Puffer würde ersetzt, ohne vorher gesichert zu werden. Gesperrt.")];
  }
  return [];
}

/**
 * Check 2: an address that happens to lie inside the image is not enough.
 * Every memory access first meets the list of protected regions
 * (data/protected.mjs), then a write has to fit a region the map declares.
 */
export function regionCheck(steps, regions = allowedRegions()) {
  const out = [];
  for (const step of steps) {
    const access = accessOf(step.msg);
    if (access?.unknown) {
      out.push(reason("fatal", "unknown-command", early(UNKNOWN_COMMAND)));
      continue;
    }
    const refused = access && refusal(access, { declared: regions });
    if (refused) {
      out.push({ ...reason("fatal", "region", early(refused.message)), protectedRegion: refused.region.id });
      continue;
    }
    const d = describeMessage(step.msg);
    if (d.kind !== "write-address") continue;
    const end = d.addr + d.length;
    const hit = regions.find(r => d.addr >= r.start && end <= r.end);
    if (!hit) {
      out.push(reason("fatal", "region",
        `Schreiben bei 0x${d.addr.toString(16)} für ${d.length} Byte liegt in keinem Bereich, den die Gerätekarte erklärt. ` +
        `Gesperrt, bevor die Simulation es sieht.`));
    }
  }
  return out;
}

/**
 * Code runs only where the editor allows it, and only what has been written
 * and read back intact: a stub that was not verified is never started.
 */
export function executeCheck(steps, executes = allowedExecutes()) {
  const out = [];
  for (const [i, step] of steps.entries()) {
    const d = describeMessage(step.msg);
    // An execute that does not call itself one is left to the dry run, whose twin refuses to run code at all.
    if (d.kind !== "execute" && step.role === "execute") {
      out.push(reason("fatal", "execute-label", "Ein Schritt, der sich Ausführen nennt, ist keine Ausführen-Nachricht. Gesperrt."));
      continue;
    }
    if (d.kind !== "execute" || step.role !== "execute") continue;
    const hit = executes.find(r => d.addr >= r.start && d.addr + 4 <= r.end);
    if (!hit) {
      out.push(reason("fatal", "execute-region", `Ausführen bei 0x${d.addr.toString(16)} ist nicht erlaubt: erlaubt sind nur der Stub-Puffer und das Leeren des Befehls-Caches. Gesperrt, bevor die Simulation es sieht.`));
    } else if (hit.stub && !steps.slice(0, i).some(s => s.role === "verify" && s.compare && s.target?.addr === d.addr)) {
      out.push(reason("fatal", "execute-unverified", `Der Code bei 0x${d.addr.toString(16)} wurde vor dem Start nicht zurückgelesen. Gesperrt.`));
    }
  }
  return out;
}

/**
 * Check 3. An error that the untouched slot already had is downgraded to a
 * warning, but only in a factory slot that is byte for byte the release:
 * there it is a gap in our knowledge. Fatal and silent stay blocked always;
 * a foreign firmware can bring a crashing preset along.
 */
export async function lintCheck(edit, ctx) {
  if (edit.kind === "patternSend") return lintPattern(edit.block);
  if (edit.kind === "sample") return lintSample(edit);
  if (edit.kind !== "fxRecord") return [];
  const after = new FxRecord(edit.bytes, edit.table);
  const before = edit.before ? new FxRecord(edit.before, edit.table) : null;
  const found = lint(after, { units: ctx.units, profile: ctx.profile });
  if (!before) return found;
  const factory = edit.slot <= FACTORY_SLOTS[edit.table] && await isOriginalSlot(before.bytes, edit.table, edit.slot);
  if (!factory) return found;
  const had = new Set(lint(before, { units: ctx.units, profile: ctx.profile }).map(f => `${f.code}:${f.where}`));
  return found.map(f => (f.severity === "error" && had.has(`${f.code}:${f.where}`)
    ? { ...f, severity: "warn", message: `Werkszustand, Wissenslücke: ${f.message}`, baseline: true }
    : f));
}

/** Check 4: the exact steps, against a copy that is thrown away afterwards. */
export function dryRun(steps, sessionDevice) {
  const scratch = new SimDevice({
    image: sessionDevice.image ? new VsbImage(sessionDevice.image.bytes) : null,
    channel: sessionDevice.channel,
    pattern: sessionDevice.pattern,
    global: sessionDevice.global,
  });
  const out = [];
  for (const [i, step] of steps.entries()) {
    // The twin cannot run code. What stands in for a dry run of an execute is the
    // rehearsal in the emulator, which the preconditions insist on.
    if (step.role === "execute" && describeMessage(step.msg).kind === "execute") continue;
    const before = scratch.faults.length;
    const reply = scratch.handle(step.msg);
    const faults = scratch.faults.slice(before);
    if (faults.length) {
      for (const f of faults) out.push(reason("fatal", f.code, `Probelauf, Schritt ${i + 1}: ${f.message}`));
      break;
    }
    if (step.expect.kind === "none") continue;
    if (!reply) { out.push(reason("fatal", "no-reply", `Probelauf, Schritt ${i + 1}: keine Antwort`)); break; }
    if (step.guard) {
      try { checkReadGuard(step, parseReadRam(reply, sessionDevice.channel, step.expect.length)); }
      catch (e) { out.push(reason("fatal", "unexpected-code", e.message)); break; }
    }
    if ((step.role === "verify" || step.role === "guard") && step.compare) {
      const got = step.expect.kind === "pattern"
        ? parsePatternDump(reply, sessionDevice.channel)
        : parseReadRam(reply, sessionDevice.channel, step.compare.length);
      const ignore = new Set(step.ignore || []);
      for (const k of ignore) got[k] = step.compare[k];
      if (got.some((b, k) => b !== step.compare[k])) {
        out.push(step.role === "guard"
          ? reason("fatal", "firmware-code", `Probelauf: Der Code bei 0x${step.target.addr.toString(16)} ist nicht der der geladenen Firmware.`)
          : reason("fatal", "verify", `Probelauf: Zurückgelesen${step.target ? ` bei 0x${step.target.addr.toString(16)}` : ""} stimmt nicht mit dem Geschriebenen überein.`));
        break;
      }
    }
  }
  return { reasons: out, device: scratch };
}

/**
 * @returns {Promise<{verdict: "blocked"|"confirm"|"clean", reasons: object[], findings: object[]}>}
 */
export async function admit(edit, steps, ctx) {
  const pre = preconditions(ctx, edit);
  if (pre.length) return { verdict: "blocked", reasons: pre, findings: [] };

  const declared = allowedRegions({ build: ctx.device?.build === "stock" ? "stock" : "hacktribe" });
  const regions = [...regionCheck(steps, declared), ...executeCheck(steps), ...backupFirst(edit, steps), ...recordAddressCheck(edit, ctx)];
  if (regions.length) return { verdict: "blocked", reasons: regions, findings: [] };

  const findings = await lintCheck(edit, ctx);
  const worst = SEVERITY_ORDER.find(s => findings.some(f => f.severity === s)) ?? null;

  // Always, whatever the steps call themselves: a step labelled a query can
  // still be a flash read that hangs the device.
  const dry = dryRun(steps, ctx.session);
  if (dry.reasons.length) return { verdict: "blocked", reasons: dry.reasons, findings };

  if (worst && BLOCKING.has(worst)) {
    return { verdict: "blocked", reasons: findings.filter(f => BLOCKING.has(f.severity)), findings };
  }
  const expert = (edit.unknownChanges || []).length;
  if (worst === "warn" || expert) {
    const extra = expert ? [reason("warn", "unknown-fields", `${expert} Änderungen an Feldern, deren Wirkung niemand kennt. Der Probelauf prüft nur, dass der Befehl ankommt.`)] : [];
    return { verdict: "confirm", reasons: [...findings.filter(f => f.severity === "warn"), ...extra], findings };
  }
  return { verdict: "clean", reasons: [], findings };
}
