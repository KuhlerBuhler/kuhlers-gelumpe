#!/usr/bin/env node
/**
 * Style analysis of the chained patterns in a set: one table per chain and the
 * recurring moves with the chains that show them. Writes markdown (German) to
 * stdout (see docs/set/uebergaenge.md). Only values are printed, never pattern bytes.
 *
 *   node tools/set/stil.mjs SET.e2sallpat > stil.md
 */
import { loadSet, chainsOf, summarize, DEST_NAME, MOTION_MFX } from "./lib.mjs";

const file = process.argv[2];
if (!file) { console.error("usage: node tools/set/stil.mjs <set.e2sallpat>"); process.exit(2); }
const set = loadSet(file);
const chains = chainsOf(set);
const sum = new Map();
const S = n => { if (!sum.has(n)) sum.set(n, summarize(set.pattern(n))); return sum.get(n); };

const bpm = t => (t / 10).toLocaleString("de-DE", { maximumFractionDigits: 1 });
const label = c => c.length > 1 ? `${c[0]} bis ${c.at(-1)}` : `${c[0]}`;
const mfxXY = s => s.motion.some(m => m.part === MOTION_MFX && (m.dest === "mfxX" || m.dest === "mfxY"));
const motionNames = s => s.motion.length ? s.motion.map(m => `${m.part === MOTION_MFX ? "MFX" : "P" + m.part} ${m.dest}`).join(", ") : "keine";
const ends = (m, i = 0) => (i ? m.values.at(-1) : m.values[0]);
const rampOf = m => { const a = m.values[0], b = Math.max(...m.values.slice(-8)); const lo = Math.min(...m.values); const hi = Math.max(...m.values); return { a, b, lo, hi }; };

const MFXNAME = { 6: "Looper", 7: "Pitch Looper" };
function changeLine(c) {
  const a = S(c[0]), z = S(c.at(-1)), bits = [];
  bits.push(`Steps ${a.steps} auf ${z.steps}`, `hörbare Parts ${a.audible} auf ${z.audible}`);
  const tempos = [...new Set(c.map(n => S(n).tempo))];
  bits.push(tempos.length === 1 ? `Tempo konstant ${bpm(a.tempo)}` : `Tempo ${tempos.map(bpm).join(", ")}`);
  const types = c.map(n => S(n).mfx);
  bits.push(new Set(types).size === 1 ? `MFX-Typ konstant ${a.mfx}` : `MFX-Typ ${types.join(" ")}`);
  const flip = c.findIndex((n, i) => i && S(n).hold !== S(c[i - 1]).hold);
  if (flip > 0) bits.push(`Hold ${S(c[flip - 1]).hold} auf ${S(c[flip]).hold} ab Pattern ${c[flip]}`);
  const xy = c.filter(n => mfxXY(S(n)));
  bits.push(xy.length ? `MFX-X/Y-Motion in ${xy.join(", ")}` : "keine MFX-X/Y-Motion");
  bits.push(`letztes Pattern: ${S(c.at(-1)).motion.length} Motion-Slots`);
  return bits.join("; ") + ".";
}

const out = [];
const w = (...x) => out.push(x.join(""));

w("# Übergänge in einem Set: der Stil, hergeleitet");
w("");
w("**Hergeleitet** aus den verketteten Patterns einer Pattern-Sicherung, ");
w("gelesen mit `tools/set/stil.mjs`. Gemessen ist nur, was in den Patterns steht; die Regeln unten sind der Schluss daraus, keine Aussage über die Absicht dahinter. Es stehen nur Werte hier, keine Pattern-Bytes.");
w("");
w("Wie die Ketten gefunden sind: jedes Pattern mit gesetztem Chain To (Byte `0x3B00`, siehe `docs/messungen/2026-10-10-pattern-kette-import.md`) wird mit seinem Ziel verbunden, ab einem Pattern, auf das keines verweist. ");
w(`Das ergibt ${chains.length} Ketten mit ${chains.reduce((a, c) => a + c.length, 0)} Patterns. Chain Repeat steht in allen auf 0 oder 1, das Gerät zeigt beides als 1. In jeder Kette verweist ein Pattern auf das mit der nächsten Nummer.`);
w("");
w("Spalten: BPM, Länge in Takten, MFX = Master-Effekt-Typ und Hold (H), Steps = alle eingeschalteten Steps in Parts mit Sample, hörbar = Parts mit Steps, Sample und ohne Mute, Motion = die automatisierten Ziele (P5 = Part 5, MFX = Master-Effekt).");
w("");

// ---- per chain tables
for (const c of chains) {
  w(`## Kette ${label(c)}`);
  w("");
  w("| Nr | Name | BPM | Takte | MFX (H) | Steps | hörbar | Motion |");
  w("|---:|---|---:|---:|---|---:|---:|---|");
  for (const n of c) {
    const s = S(n);
    w(`| ${n} | ${s.name || "(leer)"} | ${bpm(s.tempo)} | ${s.length + 1} | ${s.mfx} (${s.hold}) | ${s.steps} | ${s.audible} | ${motionNames(s)} |`);
  }
  w("");
  w(`Was sich ändert: ${changeLine(c)}`);
  w("");
}

// ---- rules
const L = c => c.at(-1), F = c => c[0];
const rules = [];
const rule = (title, chainList, text) => rules.push({ title, chainList, text });
const names = list => list.map(label).join("; ") || "keine";
const multi = chains.filter(c => c.length > 1);

// R1 end pattern without MFX X/Y motion
{
  const yes = multi.filter(c => !mfxXY(S(L(c))));
  const none = multi.filter(c => S(L(c)).motion.length === 0);
  const few = multi.filter(c => S(L(c)).motion.length <= 1);
  rule("Das Ziel ist ruhig: im letzten Pattern einer Kette hört die MFX-Bewegung auf",
    yes, `${yes.length} von ${multi.length} Ketten haben im letzten Pattern keine Motion auf Master FX X oder Y. ${none.length} davon haben dort gar keine Motion, ${few.length} höchstens einen Motion-Slot. Die Bewegung steht davor.`);
}
// R2 MFX XY motion before the end
{
  const yes = multi.filter(c => c.slice(0, -1).some(n => mfxXY(S(n))));
  const share = multi.map(c => c.slice(0, -1).filter(n => mfxXY(S(n))).length / (c.length - 1));
  rule("Der Master-Effekt wird über X und Y bewegt (Motion Sequence), in den Patterns vor dem Ziel",
    yes, `${yes.length} von ${multi.length} Ketten tragen in mindestens einem Pattern vor dem letzten Motion auf MFX X und Y. Länge der Kette gemittelt: in ${(share.reduce((a, b) => a + b, 0) / share.length * 100).toFixed(0)} % der Patterns vor dem letzten.`);
}
// R3 corner
{
  const hits = [];
  for (const c of multi) for (const n of c) {
    const xs = S(n).motion.find(m => m.part === MOTION_MFX && m.dest === "mfxX");
    const ys = S(n).motion.find(m => m.part === MOTION_MFX && m.dest === "mfxY");
    if (xs && ys && xs.values.at(-1) >= 120 && ys.values.at(-1) <= 8) hits.push([c, n]);
  }
  const chainsHit = [...new Set(hits.map(h => h[0]))];
  rule("Die Pad-Bewegung läuft in die Ecke X 127 / Y 0 bis 1 und bleibt dort",
    chainsHit, `Patterns, in denen X am Ende bei 120 oder höher und Y bei 8 oder tiefer liegt: ${hits.map(h => h[1]).join(", ")}. Kurvenform an den Patterns 77 und 189 gesehen: im ersten Teil bleibt X niedrig (etwa 20 bis 40) und Y hoch (etwa 110), im zweiten Teil steigt X auf 127 und Y fällt auf 1.`);
}
// R4 hold
{
  const yes = multi.filter(c => S(F(c)).hold === 1 && S(L(c)).hold === 0);
  const rev = multi.filter(c => S(F(c)).hold === 0 && S(L(c)).hold === 1);
  rule("MFX Hold ist am Anfang der Kette an und wird später ausgeschaltet",
    yes, `${yes.length} Ketten gehen von Hold 1 (erstes Pattern) auf 0 (letztes). Umgekehrt (0 auf 1): ${rev.length}.`);
}
// R5 MFX type
{
  const changes = multi.filter(c => S(F(c)).mfx !== S(L(c)).mfx);
  const pen = multi.filter(c => c.length >= 3).map(c => S(c.at(-2)).mfx);
  const transFx = multi.filter(c => c.slice(0, -1).some(n => [6, 7].includes(S(n).mfx) && S(n).mfx !== S(F(c)).mfx));
  const inner = new Map();
  for (const c of multi) for (const n of c.slice(1, -1)) { const t = S(n).mfx; if (t !== S(F(c)).mfx) inner.set(t, (inner.get(t) ?? 0) + 1); }
  rule("Mitten in der Kette wechselt der Master-Effekt, das Ziel setzt wieder seinen eigenen",
    changes, `In ${changes.length} von ${multi.length} Ketten ist der MFX-Typ im ersten und im letzten Pattern verschieden. Typen, die mitten in einer Kette auftauchen und vom Anfangstyp abweichen (Typ: Anzahl Patterns): ${[...inner].sort((a, b) => b[1] - a[1]).map(([t, k]) => `${t}: ${k}`).join(", ")}. Typ 6 (Looper) oder 7 (Pitch Looper) liegt in ${transFx.length} Ketten vor dem Ziel (${names(transFx)}).`);
}
// R6 density
{
  const up = multi.filter(c => S(L(c)).steps > S(F(c)).steps);
  const down = multi.filter(c => S(L(c)).steps < S(F(c)).steps);
  const ratio = multi.map(c => S(L(c)).steps / Math.max(1, S(F(c)).steps));
  const mean = ratio.reduce((a, b) => a + b, 0) / ratio.length;
  const upA = multi.filter(c => S(L(c)).audibleSteps > S(F(c)).audibleSteps);
  rule("Die Patterns werden zum Ziel hin voller, ohne dass mehr Parts klingen",
    up, `Das letzte Pattern hat mehr eingeschaltete Steps als das erste in ${up.length} von ${multi.length} Ketten, weniger in ${down.length}. Mittleres Verhältnis letztes zu erstes: ${mean.toFixed(2)} (alle Steps, auch gemutete Parts). Nur die Steps hörbarer Parts gezählt: mehr am Ende in ${upA.length} Ketten. Zusammen mit der nächsten Regel: weniger Parts klingen, aber dichter.`);
}
// R7 audible parts
{
  const fewer = multi.filter(c => S(L(c)).audible < S(F(c)).audible);
  const more = multi.filter(c => S(L(c)).audible > S(F(c)).audible);
  const lastAvg = multi.reduce((a, c) => a + S(L(c)).audible, 0) / multi.length;
  const firstAvg = multi.reduce((a, c) => a + S(F(c)).audible, 0) / multi.length;
  rule("Hörbar bleiben wenige Parts: am Ende klingen weniger als am Anfang",
    fewer, `Hörbare Parts (nicht gemutet, mit Sample und Steps): im ersten Pattern im Mittel ${firstAvg.toFixed(1)}, im letzten ${lastAvg.toFixed(1)}. Weniger am Ende in ${fewer.length} Ketten, mehr in ${more.length}. Der Rest der Parts steht gemutet im Pattern, bereit zum Einschalten.`);
}
// R8 tempo
{
  const constant = multi.filter(c => c.every(n => S(n).tempo === S(F(c)).tempo));
  const changed = multi.filter(c => !c.every(n => S(n).tempo === S(F(c)).tempo));
  const steps = [];
  for (const c of changed) for (let i = 1; i < c.length; i++) { const d = S(c[i]).tempo - S(c[i - 1]).tempo; if (d) steps.push(`${c[i - 1]} zu ${c[i]}: ${d > 0 ? "+" : ""}${bpm(d)}`); }
  const half = multi.filter(c => S(F(c)).tempo * 1.6 < S(L(c)).tempo);
  rule("Das Tempo bleibt in einer Kette gleich, geändert wird in einzelnen Sprüngen",
    constant, `${constant.length} von ${multi.length} Ketten haben durchgehend dasselbe Tempo. In den anderen: ${steps.join("; ")} (BPM). Ein deutlich langsameres erstes Pattern (Tempo des letzten durch Tempo des ersten mehr als 1,6): ${half.map(c => `${label(c)} (${bpm(S(F(c)).tempo)} auf ${bpm(S(L(c)).tempo)})`).join("; ") || "keine"}.`);
}
// R9 filter ramps
{
  const up = [], down = [], seen = new Set();
  for (const c of chains) for (const n of c) for (const m of S(n).motion) {
    if (m.dest !== "cutoff") continue;
    const r = rampOf(m);
    if (r.b - r.a > 40) up.push(n); else if (r.a - r.b > 40) down.push(n);
    seen.add(c);
  }
  const part = new Map();
  for (const c of chains) for (const n of c) for (const m of S(n).motion) if (m.dest === "cutoff") part.set(m.part, (part.get(m.part) ?? 0) + 1);
  rule("Der Filter wird über Motion Sequence geöffnet oder geschlossen, über das ganze Pattern",
    [...seen], `Cutoff-Motion in ${seen.size} Ketten. Auf (mehr als 40 Punkte): ${up.join(", ") || "-"}. Zu: ${down.join(", ") || "-"}. Parts (Part: Anzahl): ${[...part].map(([p, k]) => `${p}: ${k}`).join(", ")}. Die Kurve ist eine aufgenommene Handbewegung (ungleichmäßig), kein gerader Strich.`);
}
// R10 other automation
{
  const count = new Map();
  for (const c of chains) for (const n of c) for (const m of S(n).motion) { const k = `${m.part === MOTION_MFX ? "MFX" : "Part"} ${m.dest}`; count.set(k, (count.get(k) ?? 0) + 1); }
  rule("Was sonst automatisiert wird (Motion-Slots in Ketten)", [],
    [...count].sort((a, b) => b[1] - a[1]).map(([k, n]) => `${k}: ${n}`).join("; ") + ".");
}
// R11 mutes
{
  let flips = 0, trans = 0, stepsDelta = 0, partsTouched = 0;
  for (const c of chains) for (let i = 1; i < c.length; i++) {
    const a = S(c[i - 1]), b = S(c[i]); trans++;
    for (let p = 0; p < 16; p++) {
      if (a.parts[p].active && b.parts[p].active && a.parts[p].muted !== b.parts[p].muted) flips++;
      if (a.parts[p].active && b.parts[p].active && a.parts[p].on.length !== b.parts[p].on.length) { stepsDelta += Math.abs(a.parts[p].on.length - b.parts[p].on.length); partsTouched++; }
    }
  }
  rule("Von Pattern zu Pattern ändert sich viel an den Parts: Mutes kippen, Steps kommen und gehen", [],
    `Je Übergang (${trans} insgesamt): im Mittel ${(flips / trans).toFixed(1)} Parts wechseln den Mute-Zustand, ${(partsTouched / trans).toFixed(1)} Parts ändern ihre Step-Zahl, im Mittel um ${(stepsDelta / Math.max(1, partsTouched)).toFixed(1)} Steps.`);
}
// R12 key / swing / length
{
  const key = new Set(), swing = new Set(), len = new Map();
  for (const c of chains) for (const n of c) { const s = S(n); key.add(s.key); swing.add(s.swing); len.set(s.length + 1, (len.get(s.length + 1) ?? 0) + 1); }
  rule("Tonart und Swing bleiben, die Länge fast immer", [],
    `Tonart (Key) in allen Ketten-Patterns: ${[...key].join(", ")}; Swing: ${[...swing].join(", ")}. Länge in Takten (Anzahl Patterns): ${[...len].map(([l, k]) => `${l}: ${k}`).join(", ")}.`);
}
// R13 names
{
  const named = [];
  for (const c of chains) for (const n of c) if (S(n).name && S(n).name !== "Init Pattern") named.push(`${n} ${S(n).name}`);
  rule("Namen", [], `Ketten-Patterns mit Namen: ${named.join("; ") || "keine"}.`);
}

w("## Das Muster");
w("");
w(`Hergeleitet aus ${chains.length} Ketten. Jede Regel nennt die Ketten, die sie zeigen.`);
w("");
rules.forEach((r, i) => {
  w(`${i + 1}. **${r.title}.** ${r.text}${r.chainList.length ? ` Ketten: ${names(r.chainList)}.` : ""}`);
});
w("");
console.log(out.join("\n"));
