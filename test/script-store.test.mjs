import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STORE } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { ScriptRuntime } from "../src/script/runtime.mjs";
import { buildStore, parseStore, newestStore } from "../src/script/store.mjs";

const source = readFileSync(new URL("./fixtures/scripts/klicker-store.js", import.meta.url), "utf8");
const block = (name, text) => {
  const result = compile(text, { name });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};

test("a store file round-trips records, and a damaged file is refused", () => {
  const records = [
    { name: "klicker", mask: 0b101, values: [7, 0, -2147483648, ...new Array(13).fill(0)] },
    { name: "a", mask: 0, values: new Array(16).fill(0) },
  ];
  const bytes = buildStore({ generation: 5, records });
  assert.equal(bytes.length, STORE.headerSize + 2 * STORE.recordSize);
  const parsed = parseStore(bytes);
  assert.ok(parsed.ok);
  assert.equal(parsed.generation, 5);
  assert.deepEqual(parsed.records.map(r => [r.name, r.mask]), [["klicker", 5], ["a", 0]]);
  assert.deepEqual(Array.from(parsed.records[0].values.slice(0, 3)), [7, 0, -2147483648]);
  assert.equal(parseStore(bytes.slice(0, 10)).ok, false);
  assert.equal(parseStore(bytes.slice(0, bytes.length - 1)).reason, "abgeschnitten");
  const flipped = bytes.slice(); flipped[40] ^= 1;
  assert.equal(parseStore(flipped).reason, "Prüfsumme");
  const wrong = bytes.slice(); wrong[0] = 0;
  assert.equal(parseStore(wrong).reason, "keine Kennung");
  assert.throws(() => buildStore({ generation: 1, records: [{ name: "bad name", mask: 0, values: [] }] }), RangeError);
});

test("of two store files the newer valid one wins, and none wins when both are damaged", () => {
  const old = buildStore({ generation: 3, records: [{ name: "a", mask: 1, values: [1] }] });
  const fresh = buildStore({ generation: 4, records: [{ name: "a", mask: 1, values: [2] }] });
  assert.equal(newestStore(old, fresh).records[0].values[0], 2);
  const broken = fresh.slice(); broken[20] ^= 1;
  assert.equal(newestStore(old, broken).records[0].values[0], 1);
  assert.equal(newestStore(broken, broken.slice(0, 5)), null);
  assert.equal(newestStore(), null);
});

test("store.get falls back until a slot is set, save asks the host to write, and the saved record comes back on the next load", () => {
  let written = null;
  const storage = { load: () => null, save: records => { written = records; } };
  const first = new ScriptRuntime({ storage, frameMs: Infinity });
  assert.ok(first.add(block("klicker", source)).ok);
  first.frame();
  assert.equal(first.flushStore(), false, "nothing was saved yet");
  first.post("buttonPress", 3);
  first.post("buttonPress", 3);
  first.frame();
  assert.equal(first.storePending, true);
  assert.equal(first.flushStore(), true);
  assert.equal(first.storePending, false);
  assert.equal(written.length, 1);
  assert.equal(written[0].name, "klicker");
  assert.equal(written[0].mask, 1);
  assert.equal(written[0].values[0], 2);

  const shown = [];
  const api = { "korg.display.number": value => { shown.push(value); }, "korg.display.clear": () => {}, "korg.display.text": () => {}, "korg.led": () => {} };
  const second = new ScriptRuntime({ api, frameMs: Infinity, storage: { load: name => written.find(r => r.name === name) ?? null, save: () => {} } });
  assert.ok(second.add(block("klicker", source)).ok);
  second.frame();
  assert.deepEqual(shown, [], "the app draws nothing until it is open");
  second.openApp(0);
  second.frame();
  assert.deepEqual(shown, [2], "the count comes back after a restart");
  second.post("buttonPress", 3);
  second.frame();
  assert.deepEqual(shown, [2, 3]);
});

test("scripts do not see each other's slots and a block that uses the store needs API version 2", () => {
  const records = [];
  const rt = new ScriptRuntime({ frameMs: Infinity, storage: { load: () => null, save: r => records.push(...r) } });
  rt.add(block("one", 'korg.onEvent("buttonPress", (k) => { korg.store.set(3, 11); korg.store.save(); });'));
  rt.add(block("two", 'let seen = korg.store.get(3, -1);\nkorg.onEvent("buttonPress", (k) => { korg.store.set(3, seen + 100); korg.store.save(); });'));
  rt.frame();
  rt.post("buttonPress", 1);
  rt.frame();
  rt.flushStore();
  assert.deepEqual(records.map(r => [r.name, r.mask, r.values[3]]), [["one", 8, 11], ["two", 8, 99]]);
  const plain = compile('korg.onEvent("frame", () => { korg.led(0, 1); });', { name: "plain" });
  assert.equal(new DataView(plain.blob.buffer).getUint16(6, true), 1, "no store call, version 1 as before");
  const withStore = compile("let n = korg.store.get(0, 0);", { name: "klicker" });
  assert.equal(new DataView(withStore.blob.buffer).getUint16(6, true), 2);
});

test("a slot outside 0 to 15 ends the script with an argument error", () => {
  const rt = new ScriptRuntime({ storage: { load: () => null, save: () => {} } });
  const added = rt.add(block("bad", 'let n = 16;\nkorg.onEvent("frame", () => { korg.store.set(n, 1); });'));
  assert.ok(added.ok);
  const faults = rt.frame().faults;
  assert.equal(faults[0].name, "API_ARG");
});
