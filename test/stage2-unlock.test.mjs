import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { STAGE2_MEMORY_MARK, hasStage2Memory } from "../src/firmware.mjs";

test("the stage2-memory mark is the first word the patch writes", () => {
  const patch = JSON.parse(readFileSync(new URL("../data/patches/stage2-memory.json", import.meta.url), "utf8"));
  const first = patch.changes[0];
  assert.equal(first.file, STAGE2_MEMORY_MARK.file);
  assert.equal(first.bytes, Buffer.from(STAGE2_MEMORY_MARK.bytes).toString("hex"));
});

test("a firmware is known to carry the patch only when the mark is there", () => {
  const bytes = new Uint8Array(STAGE2_MEMORY_MARK.file + 8);
  assert.equal(hasStage2Memory(bytes), false);
  assert.equal(hasStage2Memory(undefined), false);
  bytes.set(STAGE2_MEMORY_MARK.bytes, STAGE2_MEMORY_MARK.file);
  assert.equal(hasStage2Memory(bytes), true);
});
