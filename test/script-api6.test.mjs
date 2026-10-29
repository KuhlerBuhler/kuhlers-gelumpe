import { test } from "node:test";
import assert from "node:assert/strict";
import { API_BY_NAME, API_VERSION, ARRAY_HANDLE, ERROR, EVENT_BY_NAME } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob, encodeBlob } from "../src/script/blob.mjs";
import { assemble } from "../src/script/asm.mjs";
import { loadScript } from "../src/script/vm.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { Display } from "../src/script/display.mjs";

const build = source => {
  const result = compile(source, { name: "api6" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};
const refused = source => {
  const result = compile(source, { name: "api6" });
  assert.equal(result.ok, false);
  return result.errors.map(e => e.message).join("\n");
};
const apiVersionOf = source => decodeBlob(build(source)).header.apiVersion;

/** An app that draws once with `body` when it opens. */
const app = body => `korg.app("Test", "TOOLS");\n${body.top ?? ""}\nkorg.onEvent("open", () => { korg.display.clear(); ${body.open} });`;
const opened = source => {
  const device = new SimDevice();
  assert.ok(device.load(build(source)).ok);
  device.frame();
  assert.ok(device.openApp(0));
  device.frame();
  return device;
};

test("bitmap draws the slots as columns of eight pixels, bands from the top, only lit pixels", () => {
  const device = opened(app({ top: "const pic = [1, 2, 4, 8, 16, 32, 64, 128, 255, 0, 0, 255];", open: "korg.display.bitmap(pic, 10, 2, 4);" }));
  const want = new Display();
  const slots = [1, 2, 4, 8, 16, 32, 64, 128, 255, 0, 0, 255];
  slots.forEach((bits, i) => { for (let bit = 0; bit < 8; bit++) if ((bits >> bit) & 1) want.pixel(10 + (i % 4), 2 + Math.floor(i / 4) * 8 + bit, 1); });
  assert.deepEqual(device.display.rows(), want.rows());
  assert.equal(device.display.rows().join("").split("#").length - 1, 24, "two diagonals of 4, and 8 each for the two full columns of the last band");
});

test("bitmap clips at every edge, reads whole bands only and never erases", () => {
  const d = new Display();
  d.rect(0, 0, 128, 64);
  d.clearRect(0, 0, 128, 64);
  d.bitmap([255, 255, 255, 255, 255, 255], 126, 61, 3);
  assert.deepEqual([d.get(126, 61), d.get(127, 63), d.get(127, 64), d.get(125, 61), d.get(126, 60)], [1, 1, 0, 0, 0]);
  assert.equal(d.rows().join("").split("#").length - 1, 2 * 3, "two columns by three rows are on the display");
  d.clear();
  d.bitmap([255, 255, 255, 255, 255], 0, 0, 2);
  assert.equal(d.rows().join("").split("#").length - 1, 2 * 8 * 2, "five slots at width 2 are two whole bands, the fifth slot is not read");
  d.clear();
  d.bitmap([255], -127, -63, 1);
  assert.equal(d.rows().join("").includes("#"), false, "a picture wholly beyond the left and top edge shows nothing");
  d.rect(0, 0, 4, 4);
  d.bitmap([0, 0, 0, 0], 0, 0, 4);
  assert.equal(d.get(1, 1), 1, "unlit slots erase nothing");
  d.clear();
  d.bitmap([0xFF00 | 3, 0x100 | 1], 0, 0, 2);
  assert.deepEqual([d.get(0, 0), d.get(0, 1), d.get(0, 2), d.get(1, 0), d.get(1, 1)], [1, 1, 0, 1, 0], "only the lowest 8 bits of a slot count");
});

test("bitmap at a y that is not a multiple of 8 splits each slot over two pages, also above the display", () => {
  const d = new Display();
  d.bitmap([0b10110011], 5, 5, 1);
  for (let bit = 0; bit < 8; bit++) assert.equal(d.get(5, 5 + bit), (0b10110011 >> bit) & 1, `bit ${bit}`);
  d.clear();
  d.bitmap([0b10110011], 5, -3, 1);
  for (let bit = 0; bit < 8; bit++) assert.equal(d.get(5, -3 + bit), bit < 3 ? 0 : (0b10110011 >> bit) & 1, `bit ${bit}`);
  assert.equal(d.bytes[5], 0b10110011 >> 3);
});

test("the compiler passes a global array by its first slot and length and refuses anything else there", () => {
  const blob = build("const pic = [1, 2, 3, 4]; korg.onEvent(\"frame\", () => { korg.display.bitmap(pic, 0, 0, 2); });");
  const parts = decodeBlob(blob);
  assert.ok(Array.from(parts.consts).includes(ARRAY_HANDLE.make(0, 4)));
  assert.match(refused("korg.onEvent(\"frame\", () => { korg.display.bitmap(5, 0, 0, 2); });"), /muss ein Feld sein/);
  assert.match(refused("let a = 1; korg.onEvent(\"frame\", () => { korg.display.bitmap(a, 0, 0, 2); });"), /muss ein Feld sein/);
  assert.match(refused("const pic = [1, 2]; korg.onEvent(\"frame\", () => { korg.display.bitmap(pic, 0, 0, 3); });"), /hat 2 Plätze.*Streifen zu je 3/);
  assert.match(refused("const pic = [1, 2]; let n = 1; korg.onEvent(\"frame\", () => { n = pic; });"), /ist ein Feld/);
  assert.ok(build("const pic = [1, 2]; let w = 3; korg.onEvent(\"frame\", () => { korg.display.bitmap(pic, 0, 0, w); });"), "a width that is no fixed number is the VM's business");
  assert.ok(build("const pic = new Array(32); korg.onEvent(\"frame\", () => { korg.display.bitmap(pic, 120, 60, 32); });"));
});

test("the API version of a block follows what it uses", () => {
  assert.equal(API_VERSION, 11);
  assert.equal(apiVersionOf("korg.after(100, () => { });"), 11, "a timer needs API 11");
  assert.equal(apiVersionOf("korg.onEvent(\"frame\", () => { korg.menu.blech.customizations.display.intensity = 0; });"), 10, "a path of the object tree needs API 10");
  assert.equal(apiVersionOf("let a = 0; korg.onEvent(\"touch\", (x, y) => { a = x + y; });"), 1, "a handler that takes only the old values stays as old as before");
  assert.equal(apiVersionOf("let a = 0; korg.onEvent(\"touch\", (x, y, first) => { a = first; });"), 6);
  assert.equal(apiVersionOf("const pic = [1]; korg.onEvent(\"frame\", () => { korg.display.bitmap(pic, 0, 0, 1); });"), 6);
  assert.equal(apiVersionOf("korg.onEvent(\"frame\", () => { korg.display.textNumber(\"A\", 1, 0, 0); });"), 6);
  assert.equal(apiVersionOf("korg.onEvent(\"frame\", () => { korg.display.text(\"A\", 0, 0); });"), 1);
  assert.equal(API_BY_NAME.get("korg.display.bitmap").since, 6);
  assert.equal(API_BY_NAME.get("korg.display.textNumber").since, 6);
});

/** A block that calls bitmap on the slots 2 to 5 of 8 with the given handle. */
function bitmapBlock(handle, varCount = 8) {
  const a = assemble([["HALT"], "ready:", ["PUSHK", 0], ["PUSHB", 5], ["PUSHB", 6], ["PUSHB", 2], ["CALLAPI", API_BY_NAME.get("korg.display.bitmap").id, 4], ["DROP"], ["HALT"]]);
  return encodeBlob({ apiVersion: API_VERSION, code: a.code, consts: [handle], varCount, stackMax: 4, handlers: [{ event: EVENT_BY_NAME.get("ready").id, argc: 0, entry: a.labels.get("ready") }] });
}
const run = (blob, fuel) => {
  const calls = [];
  const loaded = loadScript(blob);
  assert.ok(loaded.ok, loaded.error?.message);
  const env = { fuel, api: { "korg.display.bitmap": (...args) => calls.push(args) } };
  assert.ok(loaded.script.start(env).ok);
  return { result: loaded.script.dispatch("ready", [], env), calls };
};

test("the VM checks the handle on every call and charges the entry's fuel for each slot", () => {
  const entry = API_BY_NAME.get("korg.display.bitmap");
  const good = run(bitmapBlock(ARRAY_HANDLE.make(2, 4)));
  assert.equal(good.result.ok, true);
  assert.deepEqual(good.calls.map(c => [Array.from(c[0]), ...c.slice(1)]), [[[0, 0, 0, 0], 5, 6, 2]]);
  assert.equal(good.result.cost, 1 + 1 + 1 + 1 + 4 + entry.cost + 4 * entry.perItem + 1 + 1, "four pushes, the call op, the entry, four slots, DROP, HALT");
  for (const handle of [ARRAY_HANDLE.make(2, 0), ARRAY_HANDLE.make(5, 4), ARRAY_HANDLE.make(0xFFFF, 0xFFFF), ARRAY_HANDLE.make(8, 1)]) {
    const bad = run(bitmapBlock(handle));
    assert.equal(bad.result.code, ERROR.BAD_VAR, `handle ${handle.toString(16)}`);
    assert.equal(bad.calls.length, 0);
  }
  assert.equal(run(bitmapBlock(ARRAY_HANDLE.make(7, 1))).result.ok, true, "the last variable slot is inside");
  const need = 4 + 4 + entry.cost + 4 * entry.perItem;
  assert.equal(run(bitmapBlock(ARRAY_HANDLE.make(2, 4)), need + 2).result.ok, true);
  assert.equal(run(bitmapBlock(ARRAY_HANDLE.make(2, 4)), need).calls.length, 1, "the call itself fits, only the DROP after it does not");
  const short = run(bitmapBlock(ARRAY_HANDLE.make(2, 4)), need - 1);
  assert.equal(short.result.code, ERROR.FUEL, "a bitmap that does not fit the fuel by one unit stops");
  assert.equal(short.calls.length, 0);
  assert.equal(entry.perItem > 0 && Number.isInteger(entry.perItem), true);
});

test("textNumber is the text and the number right behind it, in one call", () => {
  const device = opened(app({ open: "korg.display.textNumber(\"BPM \", 120, 3, 5); korg.display.textNumber(\"T\", -7, 100, 40);" }));
  const want = new Display();
  want.text("BPM ", 3, 5); want.number(120, 3 + 4 * 6, 5);
  want.text("T", 100, 40); want.number(-7, 106, 40);
  assert.deepEqual(device.display.rows(), want.rows());
  const empty = opened(app({ open: "korg.display.textNumber(\"\", 42, 8, 8);" }));
  const plain = new Display(); plain.number(42, 8, 8);
  assert.deepEqual(empty.display.rows(), plain.rows());
  const edge = opened(app({ open: "korg.display.textNumber(\"Ende\", 2147483647, 100, 50);" }));
  const cut = new Display(); cut.text("Ende", 100, 50); cut.number(2147483647, 124, 50);
  assert.deepEqual(edge.display.rows(), cut.rows(), "the number is cut at the right edge like any text");
});

test("a touch carries first: 1 for the first position of a touch, 0 for the ones after it", () => {
  const seen = [];
  const source = "let n = 0; korg.onEvent(\"touch\", (x, y, first) => { n = n + 1; korg.store.set(0, first); korg.store.set(1, x); });";
  const device = new SimDevice();
  assert.ok(device.load(build(source)).ok);
  const stored = () => [device.runtime.scripts[0].store.values[0], device.runtime.scripts[0].store.values[1]];
  const touch = (x, y) => { device.post("touch", x, y); device.frame(); seen.push(stored()); };
  device.frame();
  device.post("buttonPress", 34);
  touch(100, 200);
  touch(110, 210);
  device.post("buttonRelease", 34);
  touch(5, 6);
  touch(7, 8);
  device.post("buttonPress", 34);
  touch(300, 1);
  assert.deepEqual(seen, [[1, 100], [0, 110], [1, 5], [0, 7], [1, 300]]);
});

test("zeros in an array literal need no code, because the runtime clears every variable slot", () => {
  const program = items => build(`const a = [${items}]; let x = 0; let y = 0; let z = 0; korg.onEvent("ready", () => { x = a[1]; y = a[4]; z = a[0] + a[5]; });`);
  // values above 255 keep the array in code; 0 to 255 would go to the data section
  const sparse = program("0, 500, 0, 0, 700, 0");
  const dense = program("1, 500, 1, 1, 700, 1");
  assert.ok(decodeBlob(sparse).code.length <= decodeBlob(dense).code.length - 4 * 9, "four zeros save four stores of 9 bytes");
  const loaded = loadScript(sparse);
  const env = {};
  assert.ok(loaded.script.start(env).ok);
  assert.ok(loaded.script.dispatch("ready", [], env).ok);
  assert.deepEqual(Array.from(loaded.script.vars.slice(0, 9)), [0, 500, 0, 0, 700, 0, 500, 700, 0]);
});

test("an array of bytes goes into the data section without code, trimmed of zeros at both ends", () => {
  const program = items => build(`const a = [${items}]; let x = 0; korg.onEvent("ready", () => { x = a[1] + a[4]; });`);
  const bytes = decodeBlob(program("0, 5, 0, 0, 255, 0"));
  assert.deepEqual(bytes.data.map(r => [r.base, Array.from(r.bytes)]), [[1, [5, 0, 0, 255]]]);
  assert.equal(bytes.code.length, decodeBlob(program("0, 5, 0, 0, 256, 0")).code.length - 2 * 9, "no stores for the bytes");
  assert.equal(decodeBlob(program("0, 0")).data.length, 0, "only zeros need nothing");
  const loaded = loadScript(program("0, 5, 0, 0, 255, 0"));
  const env = {};
  assert.ok(loaded.script.start(env).ok);
  assert.ok(loaded.script.dispatch("ready", [], env).ok);
  assert.deepEqual(Array.from(loaded.script.vars.slice(0, 7)), [0, 5, 0, 0, 255, 0, 260]);
});
