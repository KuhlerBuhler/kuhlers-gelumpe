import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { applyPatches, selectFor, PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { sha256 } from "../src/firmware.mjs";
import { electribePorts } from "../src/session.mjs";
import { USB_NAME_URLS } from "../src/patcher.mjs";
import { asStock, makeFirmware } from "./helpers.mjs";

// The computer sees the Electribe as "Electribe 3" (docs/ideen/69-geraetename.md): the USB string descriptors 2 to 4
// rewritten in place, the manufacturer string and the USB IDs left alone.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const SAMPLER = read("data/patches/usb-name.json");
const SYNTH = read("data/patches/usb-name-synth.json");
const file = ram => ram - 0xc0000000 + 0x100;
// per hardware: the descriptor table, and per string 2 to 4 the slot (address, length) and the old and new text
const LAYOUT = {
  sampler: { table: 0xc00a40a0, strings: [[0xc00a4120, 40, "electribe2 sampler", "Electribe 3"], [0xc00a4148, 56, "electribe2 sampler _ SOUND", "Electribe 3 SOUND"], [0xc00a4180, 60, "electribe2 sampler _ PAD/KNOB", "Electribe 3 PAD/KNOB"]] },
  synth: { table: 0xc008eb00, strings: [[0xc008eb80, 24, "electribe2", "Electribe 3"], [0xc008eb98, 40, "electribe2 _ SOUND", "Electribe 3 SOUND"], [0xc008ebc0, 44, "electribe2 _ PAD/KNOB", "Electribe 3 PAD/KNOB"]] },
};

/** A USB string descriptor: length, type 3, UTF-16LE; in a slot of `size` bytes the rest is zeros. */
const descriptor = (text, size) => {
  const out = new Uint8Array(size);
  out[0] = 2 + 2 * text.length;
  out[1] = 3;
  [...text].forEach((c, i) => { out[2 + 2 * i] = c.charCodeAt(0); });
  return out;
};

/** The text of the descriptor string `index` reads, through the table as the USB stack does. */
function stringAt(bytes, table, index) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
  const at = file(view.getUint32(file(table) + 4 * index, true));
  assert.equal(bytes[at + 1], 3, "a string descriptor");
  return Buffer.from(bytes.subarray(at + 2, at + bytes[at])).toString("utf16le");
}

/** Stand-ins for the three builds with the old descriptors and their table where the firmware keeps them. Not Korg's bytes. */
async function standIn(build) {
  let bytes;
  if (build === "synth") {
    bytes = new Uint8Array(0x200100);
    bytes.set([0x45, 0x32, 0], 0x10);
    bytes.fill(0xff, 0x170100, 0x170140);
  } else {
    bytes = await makeFirmware();
    if (build === "stock") bytes = asStock(bytes);
  }
  const { table, strings } = LAYOUT[build === "synth" ? "synth" : "sampler"];
  const view = new DataView(bytes.buffer);
  strings.forEach(([at, size, old], i) => {
    bytes.set(descriptor(old, size), file(at));
    view.setUint32(file(table) + 4 * (i + 2), at, true);
  });
  return bytes;
}

test("the usb-name patches have the v1 format, one variant per hardware, and the app knows both", () => {
  for (const patch of [SAMPLER, SYNTH]) {
    assert.equal(patch.format, PATCH_FORMAT);
    assert.equal(patch.version, 1);
    assert.equal(patch.id, "usb-name");
    assert.equal(patch.changes.length, 3);
    for (const change of patch.changes) assert.match(change.expect, /^[0-9a-f]{64}$/);
    assert.equal(patch.startPhase, undefined, "the names are read when a computer asks for them, not at start");
  }
  assert.deepEqual(SAMPLER.builds, ["hacktribe", "stock"]);
  assert.deepEqual(SYNTH.builds, ["synth"]);
  assert.deepEqual(USB_NAME_URLS, ["data/patches/usb-name.json", "data/patches/usb-name-synth.json"]);
  assert.ok(!read("data/patches/blech.json").patches.some(p => p.includes("usb-name")), "optional: not part of the BLECH set");
  assert.ok(!read("data/patches/blech-synth.json").patches.some(p => p.includes("usb-name")));
});

test("each change is one whole slot: the new descriptor, then zeros, and 'Electribe 3' in every name", () => {
  for (const [patch, hw] of [[SAMPLER, "sampler"], [SYNTH, "synth"]]) {
    LAYOUT[hw].strings.forEach(([at, size, , name], i) => {
      const change = patch.changes[i];
      assert.equal(change.file, file(at), name);
      assert.deepEqual(fromHex(change.bytes), descriptor(name, size), name);
    });
  }
});

test("the new names still match the app's port search, and SOUND and PAD/KNOB stay one device", () => {
  for (const names of [["Electribe 3 _ SOUND", "Electribe 3 _ PAD/KNOB"], ["Electribe 3 SOUND", "Electribe 3 PAD/KNOB"], ["Electribe 3", "MIDIOUT2 (Electribe 3)"]]) {
    const access = { outputs: new Map(names.map(n => [n, { name: n }])), inputs: new Map(names.map(n => [n, { name: n.replace("MIDIOUT", "MIDIIN") }])) };
    assert.deepEqual(electribePorts(access).map(p => p.name), [names[0]], names.join(", "));
  }
});

for (const build of ["hacktribe", "stock", "synth"]) {
  test(`on a ${build} stand-in the patch for it applies, the expect hashes hold and the descriptors read the new names`, async () => {
    const bytes = await standIn(build);
    const patch = build === "synth" ? SYNTH : SAMPLER;
    const { table, strings } = LAYOUT[build === "synth" ? "synth" : "sampler"];
    for (const [i, change] of patch.changes.entries()) {
      const [at, size] = strings[i];
      assert.equal(await sha256(bytes.subarray(file(at), file(at) + size)), change.expect);
    }
    const chosen = selectFor([SAMPLER, SYNTH], build);
    assert.deepEqual(chosen.reasons, []);
    assert.deepEqual(chosen.patches, [patch]);
    const res = await applyPatches(bytes, [SAMPLER, SYNTH]);
    assert.equal(res.ok, true, res.reasons.join(" "));
    assert.deepEqual([2, 3, 4].map(i => stringAt(res.bytes, table, i)), strings.map(s => s[3]));
    assert.deepEqual(res.allowCode, []);
    const other = await applyPatches(bytes, [build === "synth" ? SAMPLER : SYNTH]);
    assert.equal(other.ok, false, "the other hardware's variant is not for this build");
  });
}

const python = process.env.E2_EMU_PYTHON || new URL("../tools/emu/.venv/bin/python", import.meta.url).pathname;
for (const [label, env, path, table] of [["Hacktribe", "E2_VSB", "data/patches/usb-name.json", 0xc00a40a0], ["Korg's own 2.02", "E2_STOCK_VSB", "data/patches/usb-name.json", 0xc00a40a0], ["Korg's blue 2.02", "E2_BLUE_VSB", "data/patches/usb-name-synth.json", 0xc008eb00]]) {
  const skip = process.env[env] && existsSync(python) ? false : `set ${env}`;
  test(`${path} is what tools/patch/usb_name.py builds from your ${label} file, and it renames that file`, { skip }, async () => {
    const out = spawnSync(python, ["tools/patch/usb_name.py", "--vsb", process.env[env]], { cwd: new URL("..", import.meta.url).pathname, encoding: "utf8" });
    assert.equal(out.status, 0, out.stderr);
    assert.deepEqual(JSON.parse(out.stdout), read(path));
    const vsb = new Uint8Array(readFileSync(process.env[env]));
    assert.equal(stringAt(vsb, table, 1), "KORG INC.");
    const res = await applyPatches(vsb, [SAMPLER, SYNTH]);
    assert.equal(res.ok, true, res.reasons.join(" "));
    assert.equal(stringAt(res.bytes, table, 1), "KORG INC.", "the manufacturer stays");
    assert.match(stringAt(res.bytes, table, 2), /^Electribe 3$/);
    for (const i of [3, 4]) assert.match(stringAt(res.bytes, table, i), /^Electribe 3 (_ )?(SOUND|PAD\/KNOB)$/);
    const changed = res.bytes.reduce((n, b, i) => n + (b !== vsb[i]), 0);
    assert.ok(changed > 0 && changed <= 160, `${changed} bytes changed, all inside the three slots`);
  });
}
