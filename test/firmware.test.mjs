import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { identify, buildOf, lackOf, FEATURES, STOCK_REASON, SYNTH_REASON } from "../src/firmware.mjs";
import { makeFirmware } from "./helpers.mjs";

// Korg's own build leaves the run Hacktribe puts its code in erased; the stand-in image has it zeroed.
const HACKTRIBE_CODE = 0x170100;
const asStock = bytes => {
  const out = Uint8Array.from(bytes);
  out.fill(0xff, HACKTRIBE_CODE, HACKTRIBE_CODE + 0x40);
  return out;
};

describe("which build a firmware file is", () => {
  test("a file with Hacktribe's code in it is Hacktribe's build and the measured one", async () => {
    const bytes = await makeFirmware();
    assert.equal(buildOf(bytes), "hacktribe");
    const id = await identify(bytes);
    assert.equal(id.known, true, id.reasons.join(" "));
    assert.equal(id.build, "hacktribe");
  });

  test("a file whose presets and menus were edited is still Hacktribe's build", async () => {
    const bytes = await makeFirmware();
    bytes.fill(0x5a, 0xb5030, 0xb5030 + 0x20c);
    assert.equal(buildOf(bytes), "hacktribe");
  });

  test("Korg's own build is told apart, is not the measured one, and the reason says what it lacks", async () => {
    const id = await identify(asStock(await makeFirmware()));
    assert.equal(id.build, "stock");
    assert.equal(id.known, false);
    assert.deepEqual(id.reasons, [STOCK_REASON]);
    assert.match(id.reasons[0], /Original-Firmware/);
    assert.match(id.reasons[0], /0x52 bis 0x57/);
    assert.match(id.reasons[0], /BLECH/);
  });

  test("something that is not a Sampler image has no build", async () => {
    assert.equal((await identify(new Uint8Array(100))).build, null);
    const noPattern = asStock(await makeFirmware());
    noPattern.fill(0, 0xd0058, 0xd0058 + 4);
    const id = await identify(noPattern);
    assert.equal(id.known, false);
    assert.match(id.reasons.join(" "), /Init-Pattern/, "a stock-looking file without the Sampler's own marker is not called Korg's build");
  });

  test("Hacktribe's functions are offered for its build and refused, with the reason, for Korg's", () => {
    assert.deepEqual(FEATURES.hacktribe, { sysex: true, presets: true, patches: true });
    assert.deepEqual(FEATURES.stock, { sysex: false, presets: false, patches: true });
    assert.equal(lackOf("hacktribe"), null);
    assert.equal(lackOf("stock"), STOCK_REASON);
    assert.match(lackOf(null), /nicht erkannt/);
  });
});

describe("the blue Electribe 2 (synth)", () => {
  // The head of a synth file ends its file type in "E2" where the Sampler's has "E2S"; the stand-in has neither.
  const asSynth = async () => {
    const out = Uint8Array.from(await makeFirmware());
    out.set([0x45, 0x32, 0x00], 0x10);
    return out;
  };

  test("a file head of the synth makes it that build, not Korg's Sampler", async () => {
    assert.equal(buildOf(await asSynth()), "synth");
    const sampler = Uint8Array.from(await makeFirmware());
    sampler.set([0x45, 0x32, 0x53], 0x10);
    assert.equal(buildOf(sampler), "hacktribe");
  });

  test("it is not the measured build, and the reason is one line", async () => {
    const id = await identify(await asSynth());
    assert.equal(id.build, "synth");
    assert.equal(id.known, false);
    assert.deepEqual(id.reasons, [SYNTH_REASON]);
    assert.equal(lackOf("synth", "patches"), null);
    assert.deepEqual(FEATURES.synth, { sysex: false, presets: false, patches: true });
  });
});

const own = process.env.E2_VSB;
const stock = process.env.E2_STOCK_VSB;
const blue = process.env.E2_BLUE_VSB;

describe("the user's own files", () => {
  test("Hacktribe's file is recognised as that build", { skip: !own && "E2_VSB not set" }, async () => {
    const id = await identify(new Uint8Array(readFileSync(own)));
    assert.equal(id.build, "hacktribe");
    assert.equal(id.known, true, id.reasons.join(" "));
  });

  test("Korg's original file is recognised as that build", { skip: !stock && "E2_STOCK_VSB not set" }, async () => {
    const id = await identify(new Uint8Array(readFileSync(stock)));
    assert.equal(id.build, "stock");
    assert.equal(id.known, false);
  });

  test("the blue Electribe's file is recognised as the synth", { skip: !blue && "E2_BLUE_VSB not set" }, async () => {
    const id = await identify(new Uint8Array(readFileSync(blue)));
    assert.equal(id.build, "synth");
    assert.equal(id.known, false);
  });
});
