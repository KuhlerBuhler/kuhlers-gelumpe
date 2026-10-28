import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { VERSION_FILE, VERSION_PATCHES, VERSION_WIDTH, versionPatch } from "../tools/patch/blech_version.mjs";

const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const { version } = read("package.json");
const SETS = { "data/patches/blech.json": ["hacktribe", "stock"], "data/patches/blech-synth.json": ["synth"] };

test("blech-version carries the version of package.json (node tools/set-version.mjs rebuilds it)", () => {
  for (const { path, builds } of VERSION_PATCHES) {
    assert.equal(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"), versionPatch(version, builds), `rebuild with node tools/patch/blech_version.mjs (${path})`);
    const [change] = read(path).changes;
    const text = Buffer.from(change.bytes, "hex");
    assert.equal(text.length, VERSION_WIDTH);
    assert.equal(text.toString("latin1").replace(/\0+$/, ""), `BLECH ${version}`);
  }
});

test("the menu reads the version where the patch writes it", () => {
  const source = readFileSync(new URL("../tools/patch/script_menu.s", import.meta.url), "utf8");
  const at = Number(source.match(/^\.equ VERSION_TEXT, (0x[0-9A-Fa-f]+)/m)[1]);
  assert.equal(at - 0xC0000000 + 0x100, VERSION_FILE);
});

test("each set has the variant for its builds, and no other patch of it writes the 16 bytes", () => {
  for (const [setPath, builds] of Object.entries(SETS)) {
    const patches = read(setPath).patches.map(read);
    const mine = patches.filter(p => p.id === "blech-version");
    assert.deepEqual(mine.map(p => p.builds), [builds], setPath);
    for (const p of patches.filter(p => p.id !== "blech-version")) {
      for (const change of (p.changes ?? []).filter(c => c.field === undefined)) {   // a field change writes a mapped table, far from here
        const length = change.bytes ? change.bytes.length / 2 : change.copy.length;
        assert.ok(change.file + length <= VERSION_FILE || change.file >= VERSION_FILE + VERSION_WIDTH, `${p.id} writes ${change.file.toString(16)}`);
      }
    }
  }
});

test("a version that does not fit is refused", () => {
  assert.throws(() => versionPatch("10.100.1000"), /does not fit/);
  assert.throws(() => versionPatch("v1.2"), /not a version/);
});
