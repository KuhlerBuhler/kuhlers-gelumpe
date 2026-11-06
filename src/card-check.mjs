/**
 * Blechy's look at the SD card on the Rettung page ("Error / No File"): which .VSB files are on the card, which one fits
 * the Electribe, and the moves that put it where the firmware looks (docs/rettung.md). Only moves: nothing is deleted,
 * and a file already at that place goes aside under a new name. The card itself is behind an adapter
 * (site/app/card-access.mjs): `list()` the .VSB files as {path, size, modified}, `read(path)`, `exists(path)`,
 * `move(from, to, {replace})`.
 */
import { sha256 } from "./firmware.mjs";
import { VSB_SIZE, STOCK_SHA256, SYNTH_SHA256, HACKTRIBE_SHA256, HACKTRIBE_BLUE_SHA256 } from "./patcher.mjs";

/** The one name the firmware takes. */
export const NAME = "SYSTEM.VSB";

/** The files the app knows by their hash. */
const KNOWN = { [STOCK_SHA256]: "stock", [SYNTH_SHA256]: "synth", [HACKTRIBE_SHA256]: "hacktribe", [HACKTRIBE_BLUE_SHA256]: "hacktribeBlue" };

/**
 * "sampler" or "synth" by the head of the file (src/patcher.mjs, HEADS: byte 0x12 and 0x2E after "E2"), null for anything
 * else. The firmware compares the type in the head with the device and says "Invalid File" when it does not match.
 */
export function headOf(bytes) {
  if (bytes.length < 0x30 || bytes[0x10] !== 0x45 || bytes[0x11] !== 0x32) return null;
  if (bytes[0x12] === 0x53 && bytes[0x2e] === 0x24) return "sampler";
  if (bytes[0x12] === 0x00 && bytes[0x2e] === 0x23) return "synth";
  return null;
}

/** A file the look takes: ends in .VSB in any case, and is no "._" file a Mac writes next to every file. */
export const isVsb = name => /\.vsb$/i.test(name) && !name.startsWith("._");
/** Folders a computer keeps on the card for itself. */
export const skipDir = name => name.startsWith(".") || /^System Volume Information$/i.test(name);
/** How deep below the card the look goes; the firmware's folders are three deep. */
export const DEPTH = 6;

const dirOf = path => path.slice(0, path.lastIndexOf("/") + 1);
const nameOf = path => path.slice(path.lastIndexOf("/") + 1);
/** The card's file system does not tell upper from lower case (FAT), so neither do folders here. */
const same = (a, b) => a.toLowerCase() === b.toLowerCase();

/** What a file is: the entry with its head and, for a file the app knows, which one (`known`). Only a file of the right size is read. */
export async function identify(entry, read) {
  if (entry.size !== VSB_SIZE) return { ...entry, head: null, known: null };
  const bytes = await read(entry.path);
  if (bytes.length !== VSB_SIZE) return { ...entry, size: bytes.length, head: null, known: null };
  return { ...entry, head: headOf(bytes), known: KNOWN[await sha256(bytes)] ?? null };
}

/**
 * What is wrong with a file for `target` ({path, heads}): size, unknown (no firmware head), other (the head of the
 * other Electribe), folder, name (not SYSTEM.VSB), case (SYSTEM.VSB in other letters).
 */
export function problemsOf(file, target) {
  const out = [];
  if (file.size !== VSB_SIZE) out.push("size");
  else if (!file.head) out.push("unknown");
  else if (!target.heads.includes(file.head)) out.push("other");
  if (!same(dirOf(file.path), dirOf(target.path))) out.push("folder");
  const name = nameOf(file.path);
  if (!same(name, NAME)) out.push("name");
  else if (name !== NAME) out.push("case");
  return out;
}

const UNFIT = ["size", "unknown", "other"];
/** Whether the file is the right one for the Electribe, wherever it lies. */
export const fits = problems => !problems.some(p => UNFIT.includes(p));

/** The order to take a fitting file in: in the right folder, then below the right firmware folder, then the newest. */
function rank(target) {
  const top = target.path.split("/").slice(0, 2).join("/").toLowerCase();
  const score = f => (same(dirOf(f.path), dirOf(target.path)) ? 0 : f.path.toLowerCase().startsWith(`${top}/`) ? 1 : 2);
  return (a, b) => score(a) - score(b) || (b.modified ?? 0) - (a.modified ?? 0) || a.path.localeCompare(b.path);
}

/**
 * The look at the card for `target`: every file with its problems, and the verdict. ok: the right file is where the
 * firmware looks. fix: `steps` put it there, `file` is the one that goes there. wrong: there are files, none fits.
 * empty: no .VSB at all. A step is {op: "aside" | "move" | "rename", from, to}; an aside's `to` is the wish, the first
 * free name is taken when it runs (`applyPlan`).
 */
export function planCard(files, target) {
  const list = files.map(f => ({ ...f, problems: problemsOf(f, target) })).sort((a, b) => a.path.localeCompare(b.path));
  if (!list.length) return { verdict: "empty", files: list, steps: [] };
  const at = list.find(f => same(f.path, target.path));
  if (at && fits(at.problems)) {
    if (!at.problems.includes("case")) return { verdict: "ok", files: list, file: at, steps: [] };
    return { verdict: "fix", files: list, file: at, steps: [{ op: "rename", from: at.path, to: dirOf(at.path) + NAME }] };
  }
  const pick = list.filter(f => f !== at && fits(f.problems)).sort(rank(target))[0];
  if (!pick) return { verdict: "wrong", files: list, steps: [] };
  const steps = at ? [{ op: "aside", from: at.path, to: `${at.path}.old` }] : [];
  steps.push({ op: "move", from: pick.path, to: target.path });
  return { verdict: "fix", files: list, file: pick, steps };
}

/** The first name from `wish` on (wish, wish2, wish3 ...) that is free on the card. */
async function free(card, wish) {
  for (let n = 1; n < 100; n++) {
    const name = n === 1 ? wish : `${wish}${n}`;
    if (!await card.exists(name)) return name;
  }
  throw new Error(`${wish}: no free name`);
}

/**
 * Runs the steps of a plan on the card, in order; the first that fails stops the rest. Returns each step with the name
 * it really took and `how`: "moved", or "copied" where the card can only copy (the original then stays where it was).
 */
export async function applyPlan(card, steps) {
  const done = [];
  let replace = false;
  for (const s of steps) {
    if (s.op === "rename") {
      // a change of case only: through a free name, since the card takes both names for one
      const via = await free(card, `${s.from}.tmp`);
      const how = await card.move(s.from, via);
      await card.move(via, s.to, { replace: how === "copied" });
      done.push({ ...s, how });
    } else if (s.op === "aside") {
      const to = await free(card, s.to);
      const how = await card.move(s.from, to);
      // a copy leaves the old file at the place; what was there is kept under `to`, so the next step may write over it
      replace = how === "copied";
      done.push({ ...s, to, how });
    } else {
      done.push({ ...s, how: await card.move(s.from, s.to, { replace }) });
    }
  }
  return done;
}
