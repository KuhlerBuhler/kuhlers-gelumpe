import { test } from "node:test";
import assert from "node:assert/strict";
import { PatternFile, Pattern, FileError, parseSinglePattern, toSinglePattern, BLOCK_SIZE } from "../src/pattern.mjs";
import { fieldsOf, instances, typeOf, byteSpans, readRaw } from "../src/map/index.mjs";
import { patternDump, parsePatternDump, ReplyError } from "../src/protocol.mjs";
import { makePattern, makePatternFile } from "./helpers.mjs";

const diff = (a, b) => [...a.keys()].filter(i => a[i] !== b[i]);

/** A value of the field's type that differs from what is there now. */
function otherValue(f, current) {
  const t = typeOf(f);
  if (t.kind === "text") return current === "Zz" ? "Yy" : "Zz";
  if (t.kind === "bytes" || t.kind === "bitmap") return current.map(x => x ^ 0xff);
  const [lo, hi] = f.range || [t.min, t.max];
  return current === lo ? hi : lo;
}

test("a backup loads and saves byte for byte unchanged", () => {
  const bytes = makePatternFile();
  const file = PatternFile.parse(bytes);
  assert.equal(file.count, 250);
  assert.equal(file.name(17), "P17");
  assert.deepEqual(file.toBytes(), bytes);
});

// For every field of the pattern block, in every area of the map: change one
// instance and exactly that instance's bytes change in the saved file.
test("changing one field changes exactly its bytes, for every pattern field", () => {
  const original = makePatternFile(3);
  const header = 0x10100 + BLOCK_SIZE;          // pattern 2
  const areas = new Set();
  for (const f of fieldsOf("pattern")) {
    if (f.edit === "readonly") continue;
    areas.add(f.area);
    const all = instances(f);
    for (const ix of [all[0], all[all.length - 1]]) {
      const file = PatternFile.parse(original);
      const p = file.pattern(2);
      p.setRaw(f.id, ix, otherValue(f, p.raw(f.id, ix)));
      file.replace(2, p);
      const changed = diff(original, file.toBytes());
      const span = byteSpans({ ...f, repeat: f.repeat }).find((_, i) => i === all.indexOf(ix));
      const expected = [];
      for (let b = span[0]; b < span[1]; b++) if (original[header + b] !== file.toBytes()[header + b]) expected.push(header + b);
      assert.ok(changed.length > 0, `${f.id} ${ix}: nothing changed`);
      assert.deepEqual(changed, expected, `${f.id} ${ix}: changed bytes outside the field`);
    }
  }
  assert.deepEqual([...areas].sort(), ["master", "motion", "parts", "pattern", "steps"]);
});

test("a value set in plain words is written, and an unchanged one is not", () => {
  const p = new Pattern(makePattern());
  p.setRaw("part.modSpeed", [0], 60);
  assert.equal(p.plain("part.modSpeed", [0]).text, "1/4");
  // 60 and 56 both read 1/4. Setting 1/4 again must leave the device's 60 alone.
  assert.equal(p.setPlain("part.modSpeed", [0], p.plain("part.modSpeed", [0]).value), null);
  assert.equal(p.raw("part.modSpeed", [0]), 60);
  const change = p.setPlain("part.cutoff", [0], 652);
  assert.equal(p.raw("part.cutoff", [0]), 64);
  p.undo(change);
  assert.equal(p.raw("part.cutoff", [0]), 0xa5 & 0xff);
});

test("signed fields store two's complement in the file", () => {
  const p = new Pattern(makePattern());
  p.setRaw("part.pitch", [15], -14);
  assert.equal(p.bytes[0x800 + 15 * 0x330 + 36], 242);
  assert.equal(p.plain("part.pitch", [15]).text, "-1 Halbt.");
});

test("a broken backup is refused with a reason before anything is shown", () => {
  const good = makePatternFile(3);
  assert.throws(() => PatternFile.parse(good.subarray(0, 100)), FileError);
  const notKorg = Uint8Array.from(good); notKorg[0] = 0x58;
  assert.throws(() => PatternFile.parse(notKorg), /keine Pattern-Sicherung/);
  assert.throws(() => PatternFile.parse(good.subarray(0, good.length - 10)), /abgeschnitten/);
  const badFrame = Uint8Array.from(good); badFrame[0x10100 + BLOCK_SIZE] = 0;
  assert.throws(() => PatternFile.parse(badFrame), err => err.broken?.[0]?.pattern === 2 && /Pattern 2 beginnt nicht mit PTST/.test(err.message));
  assert.throws(() => PatternFile.parse(makePatternFile(251)), /höchstens 250/);
});

test("a shorter backup keeps its length", () => {
  const bytes = makePatternFile(5);
  assert.equal(PatternFile.parse(bytes).toBytes().length, bytes.length);
});

test("a single pattern file wraps the same block", () => {
  const p = new Pattern(makePattern({ name: "Single" }));
  const file = toSinglePattern(p);
  assert.equal(file.length, 0x100 + BLOCK_SIZE);
  assert.equal(parseSinglePattern(file).name, "Single");
  assert.throws(() => parseSinglePattern(file.subarray(10)), FileError);
});

test("the pattern buffer travels through the dump message unchanged", () => {
  const block = makePattern({ name: "Dump" });
  const msg = patternDump(9, block);
  assert.equal(msg.length, 1 + 5 + 1 + 18725 + 1);
  assert.deepEqual(parsePatternDump(msg, 9), block);
  assert.throws(() => parsePatternDump(msg, 0), ReplyError);
  const short = [...msg.slice(0, 100), 0xf7];
  assert.throws(() => parsePatternDump(short, 9), /Byte statt 16384/);
  assert.equal(readRaw(parsePatternDump(msg, 9), fieldsOf("pattern").find(f => f.id === "pattern.name")), "Dump");
});

test("a single pattern file saves byte for byte as loaded, header included", () => {
  const file = toSinglePattern(new Pattern(makePattern({ name: "Rund" })));
  file[0x30] = 0x42;                         // a header byte the device might write differently
  const p = parseSinglePattern(file);
  assert.deepEqual(toSinglePattern(p), file);
  const notSampler = Uint8Array.from(file); notSampler[0x10] = 0x58;
  assert.throws(() => parseSinglePattern(notSampler), /Electribe Sampler/);
});
