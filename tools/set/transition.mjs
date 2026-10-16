#!/usr/bin/env node
/**
 * Transition patterns between two patterns of a set, in the style of
 * docs/set/uebergaenge.md.
 *
 *   node tools/set/transition.mjs SET.e2sallpat --from 190 --to 192 [--count 2]
 *        [--direction auto|down|up|blend] [--out DIR] [--slots 201,202] [--chain]
 *        [--chain-a] [--mfx keep|N] [--tempo ease|ramp|keep] [--pad hold|release|corner|none]
 *        [--sweep tail|run|none] [--keep 3,5] [--drop 1,2] [--label NAME]
 *        [--valley auto|none|0.25] [--valley-parts 3] [--accent auto|none|16] [--clip 15|none]
 *        [--leave-max 2] [--thin-before 0.6] [--arrive pulse|all] [--insert-motion]
 *        [--all-out new.e2sallpat]
 *
 *   node tools/set/transition.mjs --a-file A.e2spat --b-file B.e2spat --slots 214,215 --slot-b 219
 *
 * The generator itself is src/transition.mjs (the editor page uses it too).
 * Output goes outside the repository, the set is never modified.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { PatternFile, parseSinglePattern, toSinglePattern } from "../../src/pattern.mjs";
import { makeTransitions, checkTransition, pickSlots, describe } from "../../src/transition.mjs";
import { loadSet, summarize } from "./lib.mjs";

export { makeTransitions, checkTransition, pickSlots, tailArc, describe } from "../../src/transition.mjs";

const fileName = it => `T${it.index}${it.slot ? `_${String(it.slot).padStart(3, "0")}` : ""}_${it.name.replace(/[^A-Za-z0-9]+/g, "-")}.e2spat`;

function parseArgs(argv) {
  const o = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    if (!x.startsWith("--")) { o._.push(x); continue; }
    const key = x.slice(2);
    if (["chain", "chain-a", "insert-motion"].includes(key)) { o[key] = true; continue; }
    o[key] = argv[++i];
  }
  return o;
}
const list = s => (s ? String(s).split(",").map(Number) : undefined);
const num = s => (s === undefined || Number.isNaN(Number(s)) ? s : Number(s));

export function main(argv) {
  const args = parseArgs(argv);
  const path = args._[0];
  const files = args["a-file"] && args["b-file"];
  if ((!files && (!path || !args.from || !args.to)) || (files && !args.slots)) {
    console.error("usage: node tools/set/transition.mjs SET.e2sallpat --from A --to B [--count 2] [--direction auto|down|up|blend] [--out DIR] [--slots 201,202] [--chain] [--chain-a] [--mfx keep|N] [--tempo ease|ramp|keep] [--pad hold|release|corner|none] [--sweep tail|run|none] [--valley auto|none|0.25] [--valley-parts 3] [--accent auto|none|16] [--clip 15|none] [--leave-max 2] [--thin-before 0.6] [--arrive pulse|all] [--insert-motion] [--keep 3,5] [--drop 1,2] [--label NAME] [--all-out NEW.e2sallpat]\n       node tools/set/transition.mjs --a-file A.e2spat --b-file B.e2spat --slots 214,215 [--slot-b 219] [--chain] [--out DIR]");
    return 2;
  }
  const set = files ? null : loadSet(path);
  const slots = args.slots ? list(args.slots) : null;
  const nA = Number(args.from ?? 0), nB = Number(args.to ?? args["slot-b"] ?? 0);
  const count = Number(args.count ?? slots?.length ?? 2);
  const a = files ? parseSinglePattern(readFileSync(args["a-file"])) : set.pattern(nA);
  const b = files ? parseSinglePattern(readFileSync(args["b-file"])) : set.pattern(nB);
  const wantSlots = slots ?? (set && (args["all-out"] || args.chain || args["chain-a"]) ? pickSlots(set, count, nA, [nA, nB]) : null);
  if (wantSlots && wantSlots.length !== count) throw new Error(`--slots needs ${count} numbers`);
  const result = makeTransitions(a, b, {
    count, direction: args.direction ?? "auto", mfx: args.mfx === undefined || args.mfx === "auto" || args.mfx === "keep" ? args.mfx : Number(args.mfx),
    tempo: args.tempo, pad: args.pad, sweep: args.sweep, label: args.label,
    valley: num(args.valley), valleyParts: args["valley-parts"] ? Number(args["valley-parts"]) : undefined, accent: num(args.accent), clip: num(args.clip),
    leaveMax: args["leave-max"] ? Number(args["leave-max"]) : undefined, thinBefore: args["thin-before"] ? Number(args["thin-before"]) : null, arrive: args.arrive, insertMotion: Boolean(args["insert-motion"]),
    keep: list(args.keep), drop: list(args.drop), slots: wantSlots, slotB: nB || undefined, chain: Boolean(args.chain),
  });
  result.items.forEach((it, k) => { it.slot = wantSlots?.[k] ?? null; });

  const out = resolve(args.out ?? join(process.env.TMPDIR ?? "/tmp", "set-demo"));
  if (out.startsWith(resolve(fileURLToPath(new URL("../..", import.meta.url))) + "/")) throw new Error("--out must lie outside the repository");
  mkdirSync(out, { recursive: true });

  let bad = false;
  for (const it of result.items) {
    const problems = checkTransition(it.pattern, a);
    for (const p of problems) { console.error(`${it.name}: ${p.severity}: ${p.message}`); if (p.severity === "error") bad = true; }
    writeFileSync(join(out, fileName(it)), toSinglePattern(it.pattern));
  }
  const text = describe(result, summarize(a), summarize(b), a, b, nA, nB);
  writeFileSync(join(out, "UEBERSICHT.txt"), text + "\n");
  console.log(text);

  const chained = (() => {
    if (!args["chain-a"] || !set) return null;
    const a2 = set.pattern(nA);
    a2.setRaw("pattern.chainTo", [], result.items[0].slot);
    a2.setRaw("pattern.chainRepeat", [], 0);
    writeFileSync(join(out, `A_${String(nA).padStart(3, "0")}_chain-to-${result.items[0].slot}.e2spat`), toSinglePattern(a2));
    return a2;
  })();

  if (args["all-out"] && set) {
    const all = new PatternFile(set.header.slice(), set.blocks.map(x => x.slice()));
    result.items.forEach(it => all.replace(it.slot, it.pattern));
    if (chained) all.replace(nA, chained);
    writeFileSync(resolve(args["all-out"]), all.toBytes());
    console.log(`\n${args["all-out"]}: Transitions in Slots ${result.items.map(i => i.slot).join(", ")}${args["chain-a"] ? `, Chain To von ${nA} auf ${result.items[0].slot}` : ""}.`);
  }
  console.log(`\nGeschrieben nach ${out}`);
  return bad ? 1 : 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exit(main(process.argv.slice(2)));
