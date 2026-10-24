import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { applyPatches, fromHex } from "../src/patch.mjs";
import { CHAINS } from "../data/hooks.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { protectTable } from "../src/sysex-table.mjs";
import { allowedRegions } from "../src/plan.mjs";
import { refusal } from "../src/protect.mjs";
import PROTECTED from "../data/protected.mjs";
import { BLECH, blechInfo, blechRead, blechBegin, blechData, classify, parseBlechInfo, parseBlechRead, parseBlechBegin, parseBlechData, BlechError, ReplyError, head, crc32, ackFor, pluginName, blechPluginBegin, describeMessage } from "../src/protocol.mjs";
import { syxEnc, syxDec, u32le } from "../src/bytes.mjs";
import EXEC from "../data/exec.mjs";
import { hasBlechSysex } from "../src/firmware.mjs";
import { sysexVectors as vectors } from "./support/sysex-vectors.mjs";

// BLECH's own SysEx commands (docs/messungen/2026-10-15-blech-sysex.md): the messages, the replies, the protection table and the patch.
const root = fileURLToPath(new URL("../", import.meta.url));
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const PATCH = read("data/patches/blech-sysex.json");
const PATCH_STOCK = read("data/patches/blech-sysex-stock.json");
const PATCHES = { hacktribe: PATCH, stock: PATCH_STOCK };
const SET = read("data/patches/blech.json");
const vsb = process.env.E2_VSB;
const stock = process.env.E2_STOCK_VSB;
const venv = join(root, "tools/emu/.venv/bin/python");
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const CODE = 0x172200;     // file offsets: 0xC0172100 + 0x100
const TABLE = 0x173900;

const words = (...v) => v.flatMap(u32le);
const answer = (fn, ...v) => [0xf0, ...head(3), fn, ...syxEnc(words(...v)), 0xf7];

test("native SysEx commands retain their bounds, CRCs and guards on both port identifiers", { timeout: 180000 }, t => {
  const probe = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
  if (probe.status && process.env.E2_ARM_REQUIRED !== "1") return t.skip("Unicorn not installed");
  assert.equal(probe.status, 0, probe.stderr);
  const result = spawnSync(python, ["-m", "unittest", "tools.patch.test_blech_sysex_buffer"], { cwd: root, encoding: "utf8", timeout: 170000 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
});

describe("the messages", () => {
  test("a request is Korg's frame with the global channel, a function byte of ours and packed little endian words", () => {
    assert.deepEqual(blechInfo(3), [0xf0, 0x42, 0x33, 0x00, 0x01, 0x24, 0x60, 0xf7]);
    const r = blechRead(3, 0xc0000040, 524);
    assert.deepEqual(r.slice(0, 7), [0xf0, 0x42, 0x33, 0x00, 0x01, 0x24, 0x61]);
    assert.deepEqual(syxDec(r.slice(7, -1)), words(0xc0000040, 524));
    assert.deepEqual(syxDec(blechBegin(3, 0xc031b310, 1024, 0xdeadbeef).slice(7, -1)), words(0xc031b310, 1024, 0xdeadbeef));
    const data = Uint8Array.from({ length: 524 }, (_, i) => (i * 5) & 0xff);
    assert.deepEqual(syxDec(blechData(3, data).slice(7, -1)), [...data], "every length, also one that leaves a remainder of six when divided by seven");
  });

  test("the function bytes collide with neither Korg's nor Hacktribe's", () => {
    const taken = [0x0e, 0x10, 0x11, 0x1c, 0x21, 0x22, 0x23, 0x24, 0x26, 0x30, 0x31, 0x32, 0x40, 0x41, 0x4c, 0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58];
    for (const fn of [BLECH.INFO, BLECH.READ, BLECH.BEGIN, BLECH.DATA, BLECH.FLASH, BLECH.FILE_READ, BLECH.FILE_BEGIN, BLECH.PLUGIN_BEGIN, BLECH.R_INFO, BLECH.R_READ, BLECH.R_BEGIN, BLECH.R_DATA, BLECH.R_FLASH, BLECH.R_FILE_READ, BLECH.R_FILE_BEGIN, BLECH.EXEC, BLECH.R_EXEC]) assert.ok(!taken.includes(fn), fn.toString(16));
    assert.equal(new Set(Object.values(BLECH).filter(v => v > 0x5f && v < 0x7f)).size, 17);
  });

  test("a plugin file's name is 1 to 16 letters, digits, _ or -, and PLUGIN BEGIN carries it padded behind the three words", () => {
    for (const ok of ["a", "Short-Delay_2", "x".repeat(16)]) assert.equal(pluginName(ok), ok);
    for (const bad of ["", "x".repeat(17), "a/b", "../x", "a.b", "a b", "\u00e4", null]) assert.equal(pluginName(bad), null);
    const msg = blechPluginBegin(3, 0, 10, 0x1234, "ab");
    assert.deepEqual(syxDec(msg.slice(7, -1)), [0, 0, 0, 0, 10, 0, 0, 0, 0x34, 0x12, 0, 0, 0x61, 0x62, ...new Array(14).fill(0)]);
    assert.equal(describeMessage(msg).kind, "file-write");
    assert.throws(() => blechPluginBegin(3, 0, 10, 0, "a/b"));
  });

  test("answers are told apart by kind, and one for another channel is not ours", () => {
    for (const [fn, kind] of [[BLECH.R_INFO, "blech-info"], [BLECH.R_READ, "blech-read"], [BLECH.R_BEGIN, "blech-begin"], [BLECH.R_DATA, "blech-data"]]) assert.equal(classify(answer(fn, 0), 3), kind);
    assert.equal(classify(answer(BLECH.R_INFO, 0), 4), "other");
  });
});

describe("the answers", () => {
  const info = answer(BLECH.R_INFO, 0, 1, 7, 0x8000, 0x662eec2a, 0);

  test("READ can name the Synth model and still rejects an answer from the other model", () => {
    const data = Uint8Array.from([1, 2, 128, 255]);
    const reply = [0xf0, 0x42, 0x33, 0, 1, 0x23, BLECH.R_READ,
      ...syxEnc([...words(0, 0xc0000000, data.length, crc32(data)), ...data]), 0xf7];
    assert.equal(blechRead(3, 0xc0000000, data.length, 0x23)[5], 0x23);
    assert.deepEqual(parseBlechRead(reply, 3, data.length, 0x23), data);
    assert.throws(() => parseBlechRead(reply, 3, data.length), ReplyError);
    assert.throws(() => blechRead(3, 0xc0000000, 4, 0x25), RangeError);
  });

  test("INFO says version, flags, the largest block and the table CRC", () => {
    assert.deepEqual(parseBlechInfo(info, 3), { version: 1, flags: 7, maxBlock: 0x8000, tableCrc: 0x662eec2a });
    assert.throws(() => parseBlechInfo(answer(BLECH.R_INFO, 0), 3), ReplyError, "too short");
  });

  test("READ gives the bytes when the length and the CRC fit, and a BlechError that may be retried when the CRC does not", () => {
    const data = Uint8Array.from({ length: 100 }, (_, i) => i * 3);
    const good = [0xf0, ...head(3), BLECH.R_READ, ...syxEnc([...words(0, 0xc0000000, 100, crc32(data)), ...data]), 0xf7];
    assert.deepEqual(parseBlechRead(good, 3, 100), data);
    const flipped = [0xf0, ...head(3), BLECH.R_READ, ...syxEnc([...words(0, 0xc0000000, 100, crc32(data)), ...data.map((b, i) => (i === 40 ? b ^ 1 : b))]), 0xf7];
    assert.throws(() => parseBlechRead(flipped, 3, 100), e => e instanceof BlechError && e.retry && e.status === BLECH.STATUS.BAD_CRC);
    assert.throws(() => parseBlechRead(good, 3, 99), ReplyError, "a length that is not the one asked for");
    for (const status of [BLECH.STATUS.REFUSED, BLECH.STATUS.RANGE]) {
      assert.throws(() => parseBlechRead(answer(BLECH.R_READ, status, 0, 0, 0), 3, 100), e => e instanceof BlechError && !e.retry && e.status === status);
    }
  });

  test("BEGIN and DATA: ok, a refusal at BEGIN, and a read-back CRC that is not the one sent", () => {
    assert.deepEqual(parseBlechBegin(answer(BLECH.R_BEGIN, 0, 0xc0000000, 16), 3), { addr: 0xc0000000, length: 16 });
    assert.throws(() => parseBlechBegin(answer(BLECH.R_BEGIN, 2, 0xc0000000, 16), 3), e => e.status === 2 && !e.retry && /verweigert/.test(e.message));
    assert.deepEqual(parseBlechData(answer(BLECH.R_DATA, 0, 1, 16, 77), 3, 77), { addr: 1, length: 16, crc: 77 });
    assert.throws(() => parseBlechData(answer(BLECH.R_DATA, 0, 1, 16, 78), 3, 77), e => e.status === BLECH.STATUS.VERIFY && !e.retry);
    assert.throws(() => parseBlechData(answer(BLECH.R_DATA, 1, 1, 16, 5), 3, 77), e => e.status === BLECH.STATUS.BAD_CRC && e.retry);
  });

  test("a write is reported to the editor as the acknowledgement Hacktribe sends", () => {
    assert.deepEqual(ackFor(3), [0xf0, 0x42, 0x33, 0x00, 0x01, 0x24, 0x21, 0xf7]);
  });
});

describe("the protection table", () => {
  const table = protectTable();
  const view = new DataView(table.bytes.buffer);

  test("it is cut from data/protected.mjs: every RAM region, with the exception windows of the three that name some", () => {
    const ram = PROTECTED.regions.filter(r => r.space === "ram");
    assert.equal(view.getUint32(0, true), ram.length);
    assert.deepEqual(table.regions.map(r => r.id), ram.map(r => r.id));
    assert.equal(table.bytes.length, 4 * (2 + 3 * ram.length + 5 * table.windows.length));
    const classes = table.regions.filter(r => r.flags & 0xff).map(r => r.id);
    assert.deepEqual(classes, PROTECTED.regions.filter(r => r.space === "ram" && r.except?.length).map(r => r.id));
    assert.deepEqual(table.regions.filter(r => r.flags & 0x100).map(r => r.id), ["loader", "dsp-ports"], "refused for reads too");
    assert.equal(table.crc, crc32(table.bytes));
  });

  for (const build of ["hacktribe", "stock"]) {
    test(`${build}: every declared window the editor writes is in a run of the table, and the runs say no more than the declared regions`, () => {
      const t = protectTable({ build });
      const declared = allowedRegions({ build });
      const names = { "firmware-image": ["table.ifx", "table.mfx", "preset.stock", "menu.ifxCount", "menu.mfxCount"], "boot-clear": ["display", "sample.name", "sample.tune"], "work-buffer": ["stub buffer"] };
      const inRuns = (cls, start, end) => t.windows.some(w => w.cls === cls && start >= w.start && ((start - w.start) % w.stride) + (end - start) <= w.width && (start - w.start) / w.stride < w.count);
      let counted = 0;
      for (const region of t.regions.filter(r => r.flags & 0xff)) {
        for (const d of declared.filter(x => names[region.id].some(p => x.what === p || x.what.startsWith(`${p} `)))) {
          assert.ok(inRuns(region.flags & 0xff, d.start, d.end), `${d.what}`);
          counted++;
        }
      }
      const covered = t.windows.reduce((n, w) => n + w.count, 0);
      assert.equal(covered, counted, "the runs hold the declared regions and nothing else");
      assert.ok(t.windows.length < 20, "998 sample names and as many tunes are two strided runs, not 1996 windows");
      assert.ok(t.bytes.length <= 0x800, "the table has to fit the room the patch keeps for it");
    });

    test(`${build}: a change to data/protected.mjs changes the table the patch carries, so the patch has to be built again`, () => {
      const bytes = PATCHES[build].changes.find(c => c.file === TABLE);
      assert.ok(bytes, "the table is a change of the patch");
      assert.deepEqual(Uint8Array.from(fromHex(bytes.bytes)), protectTable({ build }).bytes, "tools/patch/blech_sysex.mjs --vsb SYSTEM.VSB writes it");
    });
  }

  test("a build's table lets its own preset records through and refuses a record of the other build's grid", () => {
    const writes = (build, addr, length) => !refusal({ space: "ram", op: "write", addr, length }, { declared: allowedRegions({ build }) });
    assert.ok(writes("hacktribe", 0xc00a80f0, 0x20c) && writes("hacktribe", 0xc00b513c, 0x20c));
    assert.ok(writes("stock", 0xc00a7f60, 0x20c) && writes("stock", 0xc00af520 + 3 * 0x20c, 0x20c));
    assert.ok(!writes("hacktribe", 0xc00a816c, 0x20c), "Korg's second record lies across two of Hacktribe's");
    assert.ok(!writes("stock", 0xc00a80f0, 0x20c), "Hacktribe's first record lies across two of Korg's");
    assert.ok(!writes("stock", 0xc00adf94, 16), "the pointer array of Korg's build is no record");
    assert.ok(!writes("hacktribe", 0xc00a7f60, 16), "the pointer array of Hacktribe's build is no record");
  });
});

describe("the patch", () => {
  test("it has the v1 format, one file for each build that differ in the table only, says what it replaces and runs nothing at start", () => {
    for (const [build, patch] of Object.entries(PATCHES)) {
      assert.equal(patch.id, "blech-sysex");
      assert.deepEqual(patch.builds, [build]);
      assert.equal(patch.startPhase, undefined);
      for (const c of patch.changes) { assert.match(c.expect, /^[0-9a-f]{64}$/); assert.ok(c.note); assert.equal(c.copy, undefined); }
    }
    const rest = patch => ({ ...patch, builds: null, changes: patch.changes.filter(c => c.file !== TABLE) });
    assert.deepEqual(rest(PATCH), rest(PATCH_STOCK));
    assert.notDeepEqual(PATCH.changes.find(c => c.file === TABLE).bytes, PATCH_STOCK.changes.find(c => c.file === TABLE).bytes);
    assert.deepEqual(SET.patches.slice(-2), ["data/patches/blech-sysex.json", "data/patches/blech-sysex-stock.json"]);
  });

  test("two hooks, on the function byte and on the message, both before the original and both known to the registry", () => {
    assert.deepEqual(PATCH.hooks.map(h => h.site), ["0xC0026A8C", "0xC0026418"]);
    assert.deepEqual(CHAINS["sysex-request"].flatMap(s => s.sites), [0xc0026a8c, 0xc002240c, 0xc0026418, 0xc0021d70], "the Sampler's sites and the synth's");
    const code = PATCH.changes.find(c => c.file === CODE);
    for (const hook of PATCH.changes.filter(c => c.bytes.length === 8)) {
      const word = Buffer.from(fromHex(hook.bytes)).readUInt32LE(0);
      assert.equal(word >>> 24, 0xea, "a branch");
      const site = hook.file - 0x100 + 0xc0000000;
      const target = site + 8 + (((word & 0xffffff) << 8) >> 8) * 4;
      assert.ok(target >= 0xc0172100 && target < 0xc0172100 + code.bytes.length / 2, "into our code");
    }
  });

  test("with the whole set the hooks, the code and the RAM clear of every other patch's, in both builds", async () => {
    const patches = SET.patches.map(read);
    for (const build of ["hacktribe", "stock"]) {
      const { selectFor } = await import("../src/patch.mjs");
      const set = selectFor(patches, build).patches;
      assert.ok(set.some(p => p.id === "blech-sysex"));
      assert.deepEqual(checkHooks(set).reasons, [], build);
    }
  });

  test("the code and separate file workspace fit while the transfer buffer releases 19 KiB", () => {
    const ram = PATCH.ram.map(r => [Number(r.at), Number(r.at) + r.length]);
    assert.deepEqual(ram, [[0xc0191000, 0xc0191100], [0xc0191100, 0xc019a400], [0xc019f000, 0xc01a0000]]);
    const code = PATCH.changes.find(c => c.file === CODE);
    assert.ok(0xc0172100 + code.bytes.length / 2 <= 0xc0173800, "code");
    assert.ok(0xc0173800 + PATCH.changes.find(c => c.file === TABLE).bytes.length / 2 <= 0xc0174000, "table");
  });

  test("the constants of the builder are the ones of the editor", () => {
    const run = spawnSync("python3", ["-c", "import sys, json; sys.path.insert(0, 'tools/patch'); import blech_sysex as b; print(json.dumps([b.FUNC_INFO, b.FUNC_READ, b.FUNC_BEGIN, b.FUNC_DATA, b.REPLY_INFO, b.REPLY_READ, b.REPLY_BEGIN, b.REPLY_DATA, b.STATUS_OK, b.STATUS_BAD_CRC, b.STATUS_REFUSED, b.STATUS_RANGE, b.STATUS_VERIFY, b.PROTOCOL_VERSION, b.MAX_BLOCK, b.FLAGS, b.FUNC_FLASH, b.REPLY_FLASH, b.STATUS_FLASH, b.FLASH_MAX, b.FLASH_LIMIT, b.FUNC_PBEGIN, b.NAME_MAX, b.FUNC_EXEC, b.REPLY_EXEC, b.EXEC_START, b.EXEC_END]))"], { cwd: root, encoding: "utf8" });
    assert.equal(run.status, 0, run.stderr);
    const { STATUS } = BLECH;
    assert.deepEqual(JSON.parse(run.stdout), [BLECH.INFO, BLECH.READ, BLECH.BEGIN, BLECH.DATA, BLECH.R_INFO, BLECH.R_READ, BLECH.R_BEGIN, BLECH.R_DATA, STATUS.OK, STATUS.BAD_CRC, STATUS.REFUSED, STATUS.RANGE, STATUS.VERIFY, BLECH.VERSION, 0x8000, 0x7f, BLECH.FLASH, BLECH.R_FLASH, STATUS.FLASH, 0x1000, 0x1000000, BLECH.PLUGIN_BEGIN, BLECH.NAME_MAX, BLECH.EXEC, BLECH.R_EXEC, EXEC.stubAt, EXEC.stubAt + EXEC.stubSize]);
  });

  test("the synth gets read commands with a table that refuses every RAM write, in its own set", () => {
    const synth = read("data/patches/blech-sysex-synth.json");
    const table = protectTable({ build: "synth" });
    assert.equal(table.bytes.length, 20, "one region, no windows");
    assert.deepEqual(table.regions, [{ start: 0xc0000000, end: 0xc8000000, flags: 0, id: "synth-ram" }]);
    assert.deepEqual(synth.builds, ["synth"]);
    assert.equal(synth.startPhase, undefined);
    assert.deepEqual(synth.hooks.map(h => h.site), ["0xC002240C", "0xC0021D70"]);
    assert.deepEqual(Uint8Array.from(fromHex(synth.changes.find(c => c.file === TABLE).bytes)), table.bytes);
    const paths = read("data/patches/blech-synth.json").patches;
    assert.ok(paths.includes("data/patches/blech-sysex-synth.json"));
    for (const path of paths) assert.deepEqual(read(path).builds, ["synth"]);
    assert.ok(!paths.some(p => /sample-errors|synth-filters/.test(p)));
    assert.ok(!SET.patches.includes("data/patches/blech-sysex-synth.json"), "the Sampler's set has no variant for the synth, it would refuse the set");
    assert.deepEqual(checkHooks([synth]).reasons, []);
    assert.deepEqual(synth.ram.map(r => [r.at, r.length]), PATCH.ram.map(r => [r.at, r.length]));
  });

  test("the synth patch applies to the synth's file only (E2_BLUE_VSB), and a Sampler file refuses it", { skip: process.env.E2_BLUE_VSB ? false : "E2_BLUE_VSB not set" }, async () => {
    const synth = read("data/patches/blech-sysex-synth.json");
    const blue = new Uint8Array(readFileSync(process.env.E2_BLUE_VSB));
    const res = await applyPatches(blue, [synth]);
    assert.equal(res.ok, true, res.reasons.join(" "));
    assert.equal(hasBlechSysex(res.bytes), false, "the editor's check is for the Sampler's sites");
    if (vsb) assert.equal((await applyPatches(new Uint8Array(readFileSync(vsb)), [synth])).ok, false);
    assert.equal((await applyPatches(blue, [PATCH])).ok, false, "the Sampler's patch is not for the synth");
  });

  test("the nibble table is the CRC-32 of zlib: the check value of 123456789", () => {
    assert.equal(crc32(new TextEncoder().encode("123456789")), 0xcbf43926);
  });

  test("the editor tells a firmware that carries the hooks from one that does not", () => {
    const bytes = new Uint8Array(0x200100);
    assert.equal(hasBlechSysex(bytes), false);
    const view = new DataView(bytes.buffer);
    for (const [site, target] of [[0xc0026a8c, 0xc0172100], [0xc0026418, 0xc01721fc]]) view.setUint32(site - 0xc0000000 + 0x100, 0xea000000 | (((target - (site + 8)) >> 2) & 0xffffff), true);
    assert.equal(hasBlechSysex(bytes), true);
  });

  test("the builder agrees with the committed patch (E2_VSB, and E2_STOCK_VSB gives the same)", { skip: vsb ? false : "E2_VSB not set" }, async () => {
    const { buildSysexPatch } = await import("../tools/patch/blech_sysex.mjs");
    assert.deepEqual(JSON.parse(buildSysexPatch(vsb, { build: "hacktribe" })), PATCH, "node tools/patch/blech_sysex.mjs --vsb SYSTEM.VSB");
    assert.deepEqual(JSON.parse(buildSysexPatch(vsb, { build: "stock" })), PATCH_STOCK, "node tools/patch/blech_sysex.mjs --vsb SYSTEM.VSB");
    if (stock) assert.deepEqual(JSON.parse(buildSysexPatch(stock, { build: "stock" })), PATCH_STOCK);
  });

  test("applied to the own firmware it changes only what it names, nothing at start", { skip: vsb ? false : "E2_VSB not set" }, async () => {
    const original = new Uint8Array(readFileSync(vsb));
    const res = await applyPatches(original, [PATCH]);
    assert.equal(res.ok, true, res.reasons.join(" "));
    const named = PATCH.changes.map(c => [c.file, c.bytes.length / 2]);
    for (let i = 0; i < original.length; i++) if (original[i] !== res.bytes[i]) assert.ok(named.some(([at, n]) => i >= at && i < at + n), `0x${i.toString(16)}`);
    assert.equal(res.allowCode.length, 0);
    assert.equal(hasBlechSysex(res.bytes), true);
    if (stock) assert.equal((await applyPatches(new Uint8Array(readFileSync(stock)), [PATCH_STOCK])).ok, true);
  });
});

describe("the firmware's rule is the editor's rule", () => {
  test("vectors cover accepted ranges, refused ranges and out of range ones", () => {
    const v = vectors();
    assert.ok(v.length > 500);
    for (const status of [BLECH.STATUS.OK, BLECH.STATUS.REFUSED, BLECH.STATUS.RANGE]) assert.ok(v.some(x => x.status === status), String(status));
  });

  for (const build of ["hacktribe", "stock"]) {
    test(`the simulation answers them as the rule does (${build})`, async () => {
      const { SimDevice } = await import("../src/device.mjs");
      const sim = new SimDevice({ blech: true, hacktribe: build === "hacktribe" });
      for (const v of vectors(build)) assert.equal(sim.blechStatus(v.op, v.addr, v.length), v.status, `${v.op} ${v.addr.toString(16)} ${v.length}`);
    });
  }
});
