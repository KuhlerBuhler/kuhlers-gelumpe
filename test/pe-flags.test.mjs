import { test } from "node:test";
import assert from "node:assert/strict";
import { clearCfg, dllCharacteristicsAt } from "../tools/emu/pe-flags.mjs";

// A minimal PE header: MZ, pointer at 0x3c, "PE\0\0", file header, optional header.
function pe(flags) {
  const b = Buffer.alloc(0x200);
  b.write("MZ", 0, "latin1");
  b.writeUInt32LE(0x80, 0x3c);
  b.writeUInt32LE(0x4550, 0x80);
  b.writeUInt16LE(0x20b, 0x80 + 24);              // PE32+
  b.writeUInt16LE(flags, 0x80 + 24 + 70);
  return b;
}

test("clears only the CFG flag", () => {
  const b = pe(0xc160);
  assert.equal(clearCfg(b), true);
  assert.equal(b.readUInt16LE(dllCharacteristicsAt(b)), 0x8160);
  assert.equal(clearCfg(b), false);
});

test("refuses files that are not Windows programs", () => {
  assert.equal(dllCharacteristicsAt(Buffer.from("#!/bin/sh\n".padEnd(0x100))), -1);
  assert.throws(() => clearCfg(Buffer.alloc(0x100)));
});
