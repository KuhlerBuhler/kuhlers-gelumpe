import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ARCHIVE, DESC_TRAILER, ERROR } from "../data/script/contract.mjs";
import { compile } from "../src/script/compiler.mjs";
import { encodeBlob, crc32, markProbed, isProbed, decodeBlob } from "../src/script/blob.mjs";
import { packAll, parseAll, packBlech, parseBlech, describeSource } from "../src/script/archive.mjs";

const fixture = name => readFileSync(new URL(`./fixtures/scripts/${name}`, import.meta.url), "utf8");
const block = (name, source) => {
  const result = compile(source, { name });
  assert.ok(result.ok, JSON.stringify(result.errors));
  return result.blob;
};
const klicker = () => block("klicker", fixture("klicker.js"));
const snake = () => block("snake", fixture("snake.js"));

test("a collection holds blocks 4-byte aligned behind a 16 byte header with a CRC over the rest", () => {
  const blocks = [klicker(), snake()];
  const packed = packAll(blocks);
  assert.ok(packed.ok);
  const dv = new DataView(packed.bytes.buffer);
  assert.equal(dv.getUint32(0, true), ARCHIVE.magic);
  assert.equal(dv.getUint16(4, true), 1);
  assert.equal(dv.getUint16(6, true), 2);
  assert.equal(dv.getUint32(8, true), packed.bytes.length);
  assert.equal(dv.getUint32(12, true), crc32(packed.bytes, 16, packed.bytes.length));
  assert.equal(packed.bytes.length % 4, 0);
  const parsed = parseAll(packed.bytes);
  assert.ok(parsed.ok);
  assert.deepEqual(parsed.blocks.map(b => b.name), ["klicker", "snake"]);
  assert.deepEqual(parsed.blocks.map(b => b.error), [null, null]);
  assert.deepEqual(parsed.blocks[0].bytes, blocks[0]);
  assert.deepEqual(parsed.blocks[1].bytes, blocks[1]);
  assert.equal(parsed.blocks[1].offset % 4, 0);
});

test("an empty collection is valid", () => {
  const empty = packAll([]);
  assert.ok(empty.ok);
  assert.equal(empty.bytes.length, 16);
  assert.deepEqual(parseAll(empty.bytes), { ok: true, blocks: [] });
});

test("pack refuses duplicates, oversized and undecodable blocks", () => {
  assert.equal(packAll([klicker(), klicker()]).error.name, "DUPLICATE_NAME");
  const broken = klicker().slice();
  broken[60] ^= 0xff;
  assert.equal(packAll([broken]).error.code, ERROR.CHECKSUM);
  const big = encodeBlob({ name: "big", code: new Uint8Array(100), lines: Array.from({ length: 8200 }, (_, i) => ({ offset: 0, line: i })) });
  assert.ok(big.length > ARCHIVE.maxBlock);
  assert.equal(packAll([big]).error.code, ERROR.LIMITS);
  assert.equal(packAll(Array.from({ length: 65536 }, () => klicker())).error.code, ERROR.LIMITS);
});

test("parse rejects a damaged header or checksum as a whole", () => {
  const good = packAll([klicker(), snake()]).bytes;
  const with_ = (at, value) => { const copy = good.slice(); copy[at] = value; return copy; };
  assert.equal(parseAll(good.slice(0, 8)).error.code, ERROR.TRUNCATED);
  assert.equal(parseAll(with_(0, 0x58)).error.code, ERROR.MAGIC);
  assert.equal(parseAll(with_(4, 2)).error.code, ERROR.FORMAT_VERSION);
  assert.equal(parseAll(good.slice(0, good.length - 4)).error.code, ERROR.TRUNCATED);
  assert.equal(parseAll(with_(40, good[40] ^ 1)).error.code, ERROR.CHECKSUM);
  assert.equal(parseAll(with_(12, good[12] ^ 1)).error.code, ERROR.CHECKSUM);
  const resized = good.slice();
  new DataView(resized.buffer).setUint16(6, 3, true);
  const fixed = (() => { const dv = new DataView(resized.buffer); dv.setUint32(12, crc32(resized, 16, resized.length), true); return resized; })();
  assert.equal(parseAll(fixed).error.code, ERROR.TRUNCATED);
});

test("a block with a wrong checksum is reported on its own while the others stay usable", () => {
  const first = klicker();
  const second = snake().slice();
  const total = 16 + first.length + second.length;
  const out = new Uint8Array(total);
  const dv = new DataView(out.buffer);
  dv.setUint32(0, ARCHIVE.magic, true);
  dv.setUint16(4, 1, true);
  dv.setUint16(6, 2, true);
  dv.setUint32(8, total, true);
  out.set(first, 16);
  second[100] ^= 1;
  out.set(second, 16 + first.length);
  dv.setUint32(12, crc32(out, 16, total), true);
  const parsed = parseAll(out);
  assert.ok(parsed.ok);
  assert.equal(parsed.blocks[0].error, null);
  assert.equal(parsed.blocks[1].error.code, ERROR.CHECKSUM);
  assert.match(parsed.blocks[1].error.message, /Plugin 2/);
});

test("a .blech file is the block with the source behind it and the block alone stays valid", () => {
  const source = fixture("klicker.js");
  const packed = packBlech(klicker(), source);
  assert.ok(packed.ok);
  const parsed = parseBlech(packed.bytes);
  assert.ok(parsed.ok);
  assert.deepEqual(parsed.block, klicker());
  assert.equal(parsed.source, source);
  assert.equal(parsed.parts.header.name, "klicker");
  const bare = packBlech(klicker());
  assert.deepEqual(bare.bytes, klicker());
  assert.equal(parseBlech(bare.bytes).source, null);
  const umlaut = packBlech(klicker(), "// äöü ✓\n");
  assert.equal(parseBlech(umlaut.bytes).source, "// äöü ✓\n");
});

test("a .blech carries the description from the comment on top of the source, in front of the source", () => {
  const source = "// Blinks the pads, über alles.\n//\n// A second paragraph that runs over twenty characters.\nlet a = 1;\n";
  const description = describeSource(source);
  assert.equal(description, "Blinks the pads,\nueber alles.\n\nA second paragraph\nthat runs over\ntwenty characters.\n");
  assert.ok(description.split("\n").every(line => line.length <= DESC_TRAILER.width));
  const packed = packBlech(klicker(), source);
  const dv = new DataView(packed.bytes.buffer);
  assert.equal(dv.getUint32(klicker().length, true), DESC_TRAILER.magic);
  const parsed = parseBlech(packed.bytes);
  assert.equal(parsed.description, description);
  assert.equal(parsed.source, source);
  assert.equal(describeSource("let a = 1; // not on top\n"), "");
  assert.equal(parseBlech(packBlech(klicker(), "let a = 1;\n").bytes).description, null);
});

test("a damaged trailer only loses the source, a damaged block is an error", () => {
  const packed = packBlech(klicker(), "let a = 1;\n").bytes.slice();
  const cut = packed.slice(0, packed.length - 3);
  assert.equal(parseBlech(cut).source, null);
  assert.ok(parseBlech(cut).ok);
  const bad = packed.slice();
  bad[70] ^= 1;
  assert.equal(parseBlech(bad).error.code, ERROR.CHECKSUM);
  assert.equal(parseBlech(packed.slice(0, 20)).error.code, ERROR.TRUNCATED);
  assert.equal(parseBlech(new Uint8Array(40)).error.code, ERROR.MAGIC);
});

test("tools/patch/probe-flag.mjs clears and sets the flag on a .blech, keeps the source and the checksum valid", () => {
  const folder = mkdtempSync(join(tmpdir(), "probe-flag-"));
  try {
    const marked = packBlech(markProbed(block("flagged", "let a = 1;")), "let a = 1;");
    assert.ok(marked.ok);
    const original = join(folder, "in.blech");
    writeFileSync(original, marked.bytes);
    const cleared = join(folder, "cleared.blech");
    const tool = new URL("../tools/patch/probe-flag.mjs", import.meta.url).pathname;
    assert.equal(spawnSync("node", [tool, "--clear", original, cleared], { encoding: "utf8" }).status, 0);
    const parsed = parseBlech(new Uint8Array(readFileSync(cleared)));
    assert.ok(parsed.ok);
    assert.equal(parsed.source, "let a = 1;");
    assert.equal(isProbed(parsed.block), false);
    assert.equal(decodeBlob(parsed.block).ok, true);
    const again = join(folder, "again.blech");
    assert.equal(spawnSync("node", [tool, "--set", cleared, again], { encoding: "utf8" }).status, 0);
    assert.deepEqual(new Uint8Array(readFileSync(again)), new Uint8Array(readFileSync(original)));
    assert.notEqual(spawnSync("node", [tool, "--clear", join(folder, "missing.blech"), join(folder, "x")], { encoding: "utf8" }).status, 0);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
