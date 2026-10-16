import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { DOOM_LAYOUT, checkDoomLayout, currentPatches } from "../tools/doom/layout.mjs";
import { assertCandidate, validateBaseline } from "../tools/doom/validate_baseline.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const patches = currentPatches();

test("obsolete Doom region collides with current BLECH declarations", () => {
  const old = { ...DOOM_LAYOUT, bootstrap: 0xc0173000, codeEnd: 0xc017b000,
    bssEnd: 0xc0180000, shared: 0xc0180000, end: 0xc0181000 };
  assert.ok(checkDoomLayout(patches, old).some(reason => reason.includes("pattern-switch")));
});

test("v21 SysEx buffer rejects the previous Doom layout", () => {
  assert.ok(patches.some(patch => patch.id === "blech-sysex"));
  const previous = { ...DOOM_LAYOUT, bootstrap: 0xc0191000, codeEnd: 0xc0199000,
    bssEnd: 0xc019e000, shared: 0xc019e000, end: 0xc019f000 };
  assert.ok(checkDoomLayout(patches, previous).some(reason => reason.includes("blech-sysex")));
  assert.deepEqual(checkDoomLayout(patches), []);
});

test("relocated Doom code, BSS and state fit current BLECH memory declarations", () => {
  assert.deepEqual(checkDoomLayout(patches), []);
  const linker = readFileSync(resolve(root, "tools/doom/bootstrap.ld"), "utf8");
  const abi = readFileSync(resolve(root, "tools/doom/runtime_abi.h"), "utf8");
  for (const address of [DOOM_LAYOUT.bootstrap, DOOM_LAYOUT.codeEnd, DOOM_LAYOUT.bssEnd]) {
    assert.ok(linker.toLowerCase().includes(address.toString(16)), `linker address ${address.toString(16)}`);
  }
  assert.ok(abi.toLowerCase().includes(DOOM_LAYOUT.shared.toString(16)));
});

test("future patch code and runtime state in Doom space are rejected", () => {
  for (const occupant of [
    { changes: [{ file: DOOM_LAYOUT.bootstrap - 0xc0000000 + 0x100, bytes: "12345678" }] },
    { ram: [{ at: `0x${DOOM_LAYOUT.shared.toString(16)}`, length: 4, what: "future runtime" }] },
  ]) {
    assert.ok(checkDoomLayout([...patches, { id: "future", ...occupant }]).some(reason => reason.includes("future")));
  }
});

test("provenance requires the complete rebuilt image and a pinned original", async () => {
  const expected = Uint8Array.from([1, 2, 3, 4]);
  assert.doesNotThrow(() => assertCandidate(expected, expected));
  for (const changed of [Uint8Array.from([1, 2, 3, 5]), expected.subarray(0, 3)]) {
    assert.throws(() => assertCandidate(changed, expected), /vollständigen aktuellen/);
  }
  await assert.rejects(validateBaseline(expected, expected), /Originalfirmware/);
});
