import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { field, typeOf } from "../src/map/index.mjs";
import { MAX_BYTES } from "../src/loading-anim.mjs";

// Up to 1.5 the app flashed an own animation into load-bar's slot; the firmware still plays one found there when the card
// has none (tools/patch/load_bar.py), and an update keeps it (src/blech-update.mjs), so the map field stays.
const SLOT = 0xc01a6000 - 0xc0000000 + 0x100;   // tools/patch/load_bar.py:ANIM_SLOT as a file offset

test("the map field of the animation is load_bar's slot, MAX_BYTES long", () => {
  const f = field("loadingAnim");
  assert.equal(f.where.offset, SLOT);
  assert.equal(typeOf(f).width, MAX_BYTES);
  const py = readFileSync(new URL("../tools/patch/load_bar.py", import.meta.url), "utf8");
  assert.match(py, /^ANIM_SLOT = 0xC01A6000\b/m);
  assert.match(py, /^ANIM_SLOT_END = 0xC01AA000\b/m);
});
