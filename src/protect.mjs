/**
 * The list of regions the editor never writes to (data/protected.mjs), applied
 * to one access at a time.
 *
 * Two callers: the gate (src/gate.mjs, before anything is simulated) and the
 * sender (src/sender.mjs, the last step before a message leaves). The terminal
 * reaches the device through both, so a script gets the same answer as the
 * effect editor.
 */
import PROTECTED from "../data/protected.mjs";
import { allowedRegions } from "./plan.mjs";
import { describeMessage, FLASH_END } from "./protocol.mjs";

const hex = n => `0x${n.toString(16).toUpperCase()}`;

/** Every region the rule knows, with the flash limit as the last one. */
export const PROTECTED_REGIONS = [
  ...PROTECTED.regions,
  {
    id: "flash-beyond", space: "flash", start: FLASH_END, end: 0x100000000, deny: "any", status: "measured",
    what: "Hinter dem Flash",
    why: "Eine Anfrage ab dort ließ das Gerät hängen, bis es ausgeschaltet wurde.",
    evidence: "measure:2026-09-14/sysex-channel",
  },
];

export const RAM_WINDOW = PROTECTED.ram.window;

export const UNKNOWN_COMMAND = "Ein Befehl, den der Editor nicht kennt, könnte Flash beschreiben. Gesperrt.";

/** An exception names a declared region by `what` up to the first space: "table.ifx" covers "table.ifx 12". */
const covers = (what, prefixes) => prefixes?.some(p => what === p || what.startsWith(`${p} `));

/**
 * What a message does to memory, or null when it does not touch memory the
 * editor addresses. A command the editor does not know could be a flash
 * write, so it is reported as unknown and refused.
 */
export function accessOf(msg) {
  const d = describeMessage(msg);
  switch (d.kind) {
    case "write-address": return { space: "ram", op: "write", addr: d.addr, length: d.length };
    case "read-ram": return { space: "ram", op: "read", addr: d.addr, length: d.length };
    case "read-flash": return { space: "flash", op: "read", addr: d.addr, length: d.length };
    case "unknown": return { unknown: true };
    default: return null;
  }
}

/**
 * @param {{space: "ram"|"flash", op: "read"|"write", addr: number, length: number}} access
 * @param {object} [o]
 * @param {{start: number, end: number, what: string}[]} [o.declared] the regions the editor may write; the ones an exception can name
 * @returns {{region: object, message: string} | null} the reason to refuse, or null
 */
export function refusal(access, { declared, build } = {}) {
  const { space, op, addr, length } = access;
  const verb = op === "write" ? "Schreiben" : "Lesen";
  const where = `${verb} bei ${hex(addr)} für ${length} Byte`;
  let fit;
  const declaredHit = () => {
    if (fit === undefined) fit = (declared ?? allowedRegions({ build: build ?? "hacktribe" })).find(r => addr >= r.start && addr + length <= r.end) ?? null;
    return fit;
  };
  // A write to one half of the window is also a write to the other, as far as anyone knows.
  const spots = [{ at: addr, mirror: false }];
  const { start: ws, end: we } = RAM_WINDOW;
  if (space === "ram" && addr >= ws && addr + length <= we) {
    const other = addr + (addr < ws + PROTECTED.ram.mirror.distance ? 1 : -1) * PROTECTED.ram.mirror.distance;
    spots.push({ at: other, mirror: true });
  }

  for (const { at, mirror } of spots) {
    for (const region of PROTECTED_REGIONS) {
      if (region.space !== space || (region.deny === "write" && op !== "write")) continue;
      if (at >= region.end || at + length <= region.start) continue;
      if (!mirror && region.except && covers(declaredHit()?.what ?? "", region.except)) continue;
      const proposal = region.status === "proposal" ? " Schutzvorschlag, am Gerät nicht beobachtet." : "";
      const via = mirror ? ` Die Adresse liegt im vermuteten Spiegel (${hex(at)}) des Bereichs.` : "";
      return {
        region,
        message: `${where} liegt im geschützten Bereich „${region.what}“ (${hex(region.start)} bis ${hex(region.end)}): ${region.why}${via}${proposal} Gesperrt.`,
      };
    }
  }

  if (space === "ram" && (addr < ws || addr + length > we)) {
    const region = { id: "outside-window", what: "Außerhalb des vermessenen RAM-Bereichs", start: ws, end: we, space };
    return {
      region,
      message: `${where} liegt außerhalb des vermessenen RAM-Bereichs (${hex(ws)} bis ${hex(we)}). Was dort liegt, ist nicht bekannt. Gesperrt.`,
    };
  }
  return null;
}

/** The first refusal among the messages of some steps, or null. For the sender, which has no declared list of its own. */
export function refuseSteps(steps, { build } = {}) {
  for (const [i, step] of steps.entries()) {
    const access = accessOf(step.msg);
    if (!access) continue;
    if (access.unknown) return { step: i, region: { id: "unknown-command" }, message: UNKNOWN_COMMAND };
    const r = refusal(access, { build });
    if (r) return { step: i, ...r };
  }
  return null;
}
