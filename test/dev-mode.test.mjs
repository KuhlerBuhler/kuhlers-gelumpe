import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import PROTECTED from "../data/protected.mjs";
import { protectTable, DEV_OPEN } from "../src/sysex-table.mjs";
import { refusal, devClosedRegions } from "../src/protect.mjs";
import { allowedRegions } from "../src/plan.mjs";
import { BLECH } from "../src/protocol.mjs";
import { sysexVectors } from "./support/sysex-vectors.mjs";

// DEV MODE (docs/messungen/2026-11-14-dev-mode-sperrbereiche.md): with it on, BLECH WRITE may write the firmware image in RAM,
// except the regions that carry a write or a flash write. The firmware's half is tools/patch/blech_sysex.py, its emulator
// cases the DEV MODE group of tools/emu/sysex_cases.py.
const root = fileURLToPath(new URL("../", import.meta.url));
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const venv = join(root, "tools/emu/.venv/bin/python");
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const IMAGE = [0xc0000000, 0xc0200000];
const DEV_FLAG = 0xc01910fc;

describe("the table with DEV MODE", () => {
  test("bit 9 is set on the firmware image and nowhere else, on hacktribe and stock", () => {
    for (const build of ["hacktribe", "stock"]) {
      const t = protectTable({ build });
      assert.deepEqual(t.regions.filter(r => r.flags & DEV_OPEN).map(r => r.id), ["firmware-image"], build);
      assert.ok(t.bytes.length <= 0x800, `${build}: ${t.bytes.length} bytes fit the room of the table`);
    }
  });

  test("the synth's table is the same 20 bytes as before: one region, no bit 9, nothing closed on top", () => {
    const t = protectTable({ build: "synth" });
    assert.deepEqual([...t.bytes], [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xc0, 0, 0, 0, 0xc8, 0, 0, 0, 0]);
  });

  for (const build of ["hacktribe", "stock"]) {
    test(`${build}: the closed regions lie in the image, in order, apart, with flags 0, and cover no write the editor declares`, () => {
      const closed = PROTECTED.devClosed[build];
      assert.ok(closed.length > 10);
      const t = protectTable({ build });
      for (const [i, r] of closed.entries()) {
        assert.ok(r.start >= IMAGE[0] && r.end <= IMAGE[1] && r.start < r.end, `${r.start.toString(16)}`);
        if (i) assert.ok(closed[i - 1].end <= r.start, `overlap at ${r.start.toString(16)}`);
        assert.ok(t.regions.some(x => x.start === r.start && x.end === r.end && x.flags === 0));
      }
      for (const d of allowedRegions({ build })) {
        const hit = closed.find(r => d.start < r.end && d.end > r.start);
        assert.equal(hit, undefined, `${d.what} lies in a closed region`);
      }
      assert.ok(closed.some(r => r.start <= DEV_FLAG && r.end >= DEV_FLAG + 4), "DEV_FLAG itself is closed");
    });
  }

  test("data/dev-closed.mjs is what the constants of blech_sysex.py and the trace files give", () => {
    const run = spawnSync(python, ["tools/emu/sysex_trace.py", "closed", "--check"], { cwd: root, encoding: "utf8" });
    assert.equal(run.status, 0, run.stderr);
  });

  test("the builder's constants are the editor's", () => {
    const run = spawnSync("python3", ["-c", "import sys, json; sys.path.insert(0, 'tools/patch'); import blech_sysex as b; print(json.dumps([b.FLAG_DEV, b.FLAG_DEV_ON, b.DEV_OPEN, b.DEV_FLAG]))"], { cwd: root, encoding: "utf8" });
    assert.equal(run.status, 0, run.stderr);
    assert.deepEqual(JSON.parse(run.stdout), [BLECH.FLAG_DEV, BLECH.FLAG_DEV_ON, DEV_OPEN, DEV_FLAG]);
  });

  test("no patch of the sets writes DEV_FLAG, so a built image starts with DEV MODE off", () => {
    for (const file of ["blech-sysex.json", "blech-sysex-stock.json", "blech-sysex-synth.json"]) {
      for (const c of read(`data/patches/${file}`).changes) {
        const at = 0xc0000000 + c.file - 0x100;   // a change names its offset in the VSB, behind the 0x100-byte head
        const end = at + (c.bytes?.length ?? 0) / 2;
        assert.ok(end <= DEV_FLAG || at >= DEV_FLAG + 4, `${file}: a change at ${at.toString(16)} covers DEV_FLAG`);
      }
    }
  });
});

describe("src/protect.mjs with DEV MODE", () => {
  const write = (addr, length = 16) => ({ space: "ram", op: "write", addr, length });

  test("off, a write into the image is refused as before; on, it passes", () => {
    assert.equal(refusal(write(0xc0100000)).region.id, "firmware-image");
    assert.equal(refusal(write(0xc0100000), { devMode: true }), null);
    assert.equal(refusal(write(0xc0100000), { devMode: true, build: "stock" }), null);
  });

  test("on, every closed region refuses at its first byte, its last word and across its lower edge", () => {
    for (const build of ["hacktribe", "stock"]) {
      for (const r of devClosedRegions(build)) {
        for (const [addr, length] of [[r.start, 1], [r.end - 4, 4], [r.start - 4, 8]]) {
          const got = refusal(write(addr, length), { devMode: true, build });
          assert.ok(got && got.region.id.startsWith("dev-closed-"), `${build} ${addr.toString(16)}`);
        }
      }
    }
  });

  test("on, the image's mirror, the regions outside the image and the synth stay refused", () => {
    assert.equal(refusal(write(0xc4100000), { devMode: true }).region.id, "firmware-image");
    assert.equal(refusal(write(0xc0210000), { devMode: true }).region.id, "task-stacks");
    assert.equal(refusal(write(0xc01ffff0), { devMode: true, build: "hacktribe" })?.region.id ?? null, null);
    assert.equal(refusal(write(0xc0100000), { devMode: true, build: "synth" }).region.id, "firmware-image");
  });

  test("a read is not changed by DEV MODE", () => {
    const read = { space: "ram", op: "read", addr: 0xc0172100, length: 64 };
    assert.equal(refusal(read, { devMode: true }), refusal(read));
  });

  test("the dev vectors are marked and differ from the plain ones only inside the image", () => {
    const plain = new Map(sysexVectors("hacktribe").map(v => [`${v.op}:${v.addr}:${v.length}`, v.status]));
    const dev = sysexVectors("hacktribe", { devMode: true });
    assert.ok(dev.every(v => v.dev === true));
    for (const v of dev) {
      const before = plain.get(`${v.op}:${v.addr}:${v.length}`);
      if (before === undefined || before === v.status) continue;
      assert.ok(v.op === "write" && v.addr >= IMAGE[0] && v.addr + v.length <= IMAGE[1], `${v.addr.toString(16)}`);
    }
    assert.ok(dev.some(v => v.op === "write" && v.status === BLECH.STATUS.OK && v.addr >= IMAGE[0] && v.addr + v.length <= IMAGE[1]), "some image writes pass");
  });
});

describe("the remote mailbox: user input over USB with DEV MODE", () => {
  const box = PROTECTED.remoteMailbox;
  const write = (addr, length) => ({ space: "ram", op: "write", addr, length });

  test("is where script_remote.s keeps the message, the command word and the done counter", () => {
    const card = Number(readFileSync(join(root, "tools/patch/script_hooks.py"), "utf8").match(/^CARD = (0x\w+)/m)[1]);
    const s = readFileSync(join(root, "tools/patch/script_remote.s"), "utf8");
    const equ = name => Number(s.match(new RegExp(`^\\.equ ${name}, (\\w+)`, "m"))[1]);
    assert.equal(box.start, card + equ("RM_MSG_AT"));
    assert.equal(box.end, card + equ("RM_AT") + equ("RM_SIZE"));
  });

  for (const build of ["hacktribe", "stock"]) {
    test(`${build}: the message and the command word are written with DEV MODE on and refused with it off`, () => {
      for (const [addr, length] of [[box.start, 8], [box.end - 12, 4], [box.end - 4, 4]]) {
        assert.equal(refusal(write(addr, length), { devMode: true, build }), null, `${addr.toString(16)}`);
        assert.equal(refusal(write(addr, length), { build }).region.id, "firmware-image", `${addr.toString(16)}`);
      }
      assert.equal(devClosedRegions(build).find(r => r.start < box.end && r.end > box.start), undefined, "no closed region covers the mailbox");
    });
  }

  test("the synth refuses it even with the flag", () => {
    assert.equal(refusal(write(box.start, 8), { devMode: true, build: "synth" }).region.id, "firmware-image");
  });

  test("the DEV vectors ask the firmware about the mailbox, the plain ones expect a refusal there", () => {
    const at = v => v.op === "write" && v.addr === box.start && v.length === 4;
    assert.equal(sysexVectors("hacktribe", { devMode: true }).find(at).status, BLECH.STATUS.OK);
  });
});
