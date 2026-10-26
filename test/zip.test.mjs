import { test } from "node:test";
import assert from "node:assert/strict";
import { isZip, unzipEntry } from "../src/zip.mjs";
import { makeZip as zip } from "./helpers.mjs";

const vsb = Uint8Array.from({ length: 70000 }, (_, i) => (i * 7) & 0xff);

test("SYSTEM.VSB comes out of a zip as Korg ships it, deflated or stored, the macOS copies left aside", async () => {
  for (const method of [0, 8]) {
    const archive = zip([
      { name: "__MACOSX/electribe_sampler_system_v202/._SYSTEM.VSB", bytes: Uint8Array.of(1, 2, 3) },
      { name: "electribe_sampler_system_v202/Release Note.pdf", bytes: Uint8Array.of(9, 9) },
      { name: "electribe_sampler_system_v202/SYSTEM.VSB", bytes: vsb, method },
    ]);
    assert.equal(isZip(archive), true);
    const got = await unzipEntry(archive);
    assert.equal(got.name, "electribe_sampler_system_v202/SYSTEM.VSB");
    assert.deepEqual(got.bytes, vsb);
  }
});

test("a zip without SYSTEM.VSB gives null, a broken one says so, a VSB is no zip", async () => {
  assert.equal(await unzipEntry(zip([{ name: "readme.txt", bytes: Uint8Array.of(1) }])), null);
  await assert.rejects(unzipEntry(Uint8Array.of(0x50, 0x4b, 3, 4, 0, 0)), /kein lesbares Zip-Archiv/);
  const cut = zip([{ name: "SYSTEM.VSB", bytes: vsb }]);
  cut[cut.length - 22 + 16] ^= 0x40;
  await assert.rejects(unzipEntry(cut), /beschädigt/);
  assert.equal(isZip(vsb), false);
});
