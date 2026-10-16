#!/usr/bin/env node
/**
 * Sets or clears the PROBED flag of a script block (the editor sets it on export) and makes the checksum
 * again. Works on a .blech (the source trailer stays) or a single block. For trying the device's one-time
 * question about scripts that did not come out of the editor.
 *
 *   node tools/patch/probe-flag.mjs --clear in.blech out.blech
 *   node tools/patch/probe-flag.mjs --set in.blech out.blech
 */
import { readFileSync, writeFileSync } from "node:fs";
import { decodeBlob, markProbed } from "../../src/script/blob.mjs";
import { HEADER } from "../../data/script/contract.mjs";

const [mode, input, output] = process.argv.slice(2);
if (!["--set", "--clear"].includes(mode) || !input || !output) {
  process.stderr.write("usage: probe-flag.mjs (--set | --clear) in.blech out.blech\n");
  process.exit(2);
}
const bytes = new Uint8Array(readFileSync(input));
const total = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(HEADER.fields.find(f => f.name === "totalSize").offset, true);
if (!(total >= HEADER.size && total <= bytes.length)) {
  process.stderr.write("not a script block: the size in the header does not fit the file\n");
  process.exit(1);
}
const block = markProbed(bytes.subarray(0, total), mode === "--set");
const decoded = decodeBlob(block);
if (!decoded.ok) {
  process.stderr.write(`the block does not decode: ${decoded.error.message}\n`);
  process.exit(1);
}
const out = new Uint8Array(bytes.length);
out.set(block);
out.set(bytes.subarray(total), total);
writeFileSync(output, out);
console.log(`${output}: flag ${mode === "--set" ? "set" : "cleared"}, block ${total} bytes, trailer ${bytes.length - total} bytes`);
