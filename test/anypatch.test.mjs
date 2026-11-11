import { test } from "node:test";
import assert from "node:assert/strict";
import { readAnyPatch, applyAnyPatch, itemsOf, OWN_ID } from "../src/anypatch.mjs";
import { VSB_SIZE } from "../src/patcher.mjs";
import { sha256 } from "../src/firmware.mjs";
import { render } from "../src/text.mjs";
import { makeFirmware } from "./helpers.mjs";
import { expected, fixture, oldFile } from "./fixtures/bsdiff/data.mjs";

const FREE = 0x1a2100;
const ascii = text => Uint8Array.from(text, c => c.charCodeAt(0));
const be = (n, width) => Array.from({ length: width }, (_, i) => (n >>> (8 * (width - 1 - i))) & 0xff);
/** An IPS file: a record is [offset, bytes] or [offset, length, fill] for a run. */
const ips = (records, { wide = false, cut = null, end = wide ? "EEOF" : "EOF" } = {}) => Uint8Array.from([
  ...ascii(wide ? "IPS32" : "PATCH"),
  ...records.flatMap(([offset, a, fill]) => [...be(offset, wide ? 4 : 3), ...(typeof a === "number" ? [0, 0, ...be(a, 2), fill] : [...be(a.length, 2), ...a])]),
  ...ascii(end),
  ...(cut === null ? [] : be(cut, wide ? 4 : 3)),
]);
const rejects = (bytes, key) => assert.rejects(readAnyPatch(bytes), e => e.text?.key === key);

test("an IPS patch is read and laid over a firmware: data records and runs, only those bytes change", async () => {
  const vsb = await makeFirmware();
  const patch = ips([[FREE, [1, 2, 3, 4]], [FREE + 0x100, 16, 0xab]]);
  const own = await readAnyPatch(patch);
  assert.equal(own.kind, "ips");
  assert.equal(render(own.label), "IPS-Patch, 2 Änderungen");
  const res = await applyAnyPatch(vsb, own);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal(res.bytes.length, VSB_SIZE);
  assert.deepEqual([...res.bytes.subarray(FREE, FREE + 4)], [1, 2, 3, 4]);
  assert.deepEqual([...res.bytes.subarray(FREE + 0x100, FREE + 0x110)], Array(16).fill(0xab));
  assert.deepEqual(res.spans.map(s => [s.patch, s.file, s.length]), [[OWN_ID, FREE, 4], [OWN_ID, FREE + 0x100, 16]]);
  assert.deepEqual(res.bytes.subarray(0, FREE), vsb.subarray(0, FREE), "nothing before the records moved");
  assert.deepEqual(itemsOf(own, vsb, () => "x").map(i => i.id), [OWN_ID]);
});

test("an IPS32 patch with 4-byte offsets works the same", async () => {
  const vsb = await makeFirmware();
  const own = await readAnyPatch(ips([[FREE, [9, 8, 7]]], { wide: true }));
  const res = await applyAnyPatch(vsb, own);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual([...res.bytes.subarray(FREE, FREE + 3)], [9, 8, 7]);
});

test("an IPS patch that writes past the end, or leaves the file at another size, is refused with its reason", async () => {
  const vsb = await makeFirmware();
  const past = await applyAnyPatch(vsb, await readAnyPatch(ips([[VSB_SIZE - 2, [1, 2, 3, 4]]])));
  assert.equal(past.ok, false);
  assert.match(past.reasons[0], /hinter das Ende der Firmware/);
  const cut = await applyAnyPatch(vsb, await readAnyPatch(ips([[FREE, [1]]], { cut: 0x1000 })));
  assert.equal(cut.ok, false);
  assert.match(cut.reasons[0], /keine SYSTEM\.VSB/);
});

test("a gelumpe-patch in JSON, alone or in a list, goes through applyPatches", async () => {
  const vsb = await makeFirmware();
  const patch = { format: "gelumpe-patch", version: 1, id: "raw", name: "Raw", changes: [{ file: FREE, bytes: "e12fff1e", expect: await sha256(vsb.subarray(FREE, FREE + 4)) }] };
  for (const body of [patch, [patch]]) {
    const own = await readAnyPatch(new TextEncoder().encode(JSON.stringify(body)));
    assert.equal(own.kind, "json");
    assert.deepEqual(itemsOf(own, vsb, p => p.name), [{ id: "raw", label: "Raw" }]);
    const res = await applyAnyPatch(vsb, own);
    assert.equal(res.ok, true, res.reasons.join(" "));
    assert.deepEqual([...res.bytes.subarray(FREE, FREE + 4)], [0xe1, 0x2f, 0xff, 0x1e]);
  }
});

test("a bsdiff patch is applied to a firmware-sized file, and the changed runs come back as spans", async () => {
  const own = await readAnyPatch(fixture("./patch/edit.patch"));
  assert.equal(own.kind, "bsdiff");
  assert.equal(render(own.label), "bsdiff-Patch");
  const res = await applyAnyPatch(oldFile(), own);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal(await sha256(res.bytes), expected.patch.new);
  assert.ok(res.spans.length > 0 && res.spans.every(s => s.patch === OWN_ID));
});

test("what is no patch gets a clear error: empty, unknown, a format that is named but not applied, a cut-off IPS", async () => {
  await rejects(new Uint8Array(0), "patcher.any.empty");
  await rejects(ascii("this is a text file, not a patch"), "patcher.any.unknown");
  await rejects(ascii("{\"hello\": 1}"), "patcher.any.json");
  await rejects(ascii("not { json"), "patcher.any.unknown");
  await rejects(ips([[FREE, [1, 2, 3]]]).subarray(0, 12), "patcher.any.ips.bad");
  await rejects(ips([[FREE, [1]]], { end: "EOX" }), "patcher.any.ips.bad");
  await assert.rejects(readAnyPatch(ascii("BPS1....")), e => e.text.key === "patcher.any.unsupported" && e.text.vars.format === "BPS");
  await assert.rejects(readAnyPatch(Uint8Array.of(0xd6, 0xc3, 0xc4, 0, 0)), e => e.text.vars.format === "xdelta");
  assert.match((await readAnyPatch(ascii("PATCH")).catch(e => e)).message, /IPS-Patch ist abgeschnitten/);
});
