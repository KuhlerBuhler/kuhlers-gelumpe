import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { remoteMailbox, command, stub, KEY, ENCODER } from "../src/remote.mjs";
import { makeKorg } from "../src/korg.mjs";
import { ramToFile } from "../src/map/address.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const MAILBOX = 0xc01f7fc0;

/** A firmware file long enough for the runtime's code area, with the signature of tools/patch/script_remote.s or without. */
function image(signed) {
  const bytes = new Uint8Array(ramToFile(0xc0190000)).fill(0xff);
  if (signed) {
    const view = new DataView(bytes.buffer);
    view.setUint32(ramToFile(0xc018eb18), 0x544d4552, true);
    view.setUint32(ramToFile(0xc018eb1c), MAILBOX, true);
  }
  return bytes;
}

test("a key and a turn of the dial become marked command words, and bad values are refused", () => {
  assert.equal(command(KEY, 0x09), 0xa5000901);
  assert.equal(command(ENCODER, 0, -1), 0xa5ff0002);
  assert.equal(command(ENCODER, 0, 3), 0xa5030002);
  assert.throws(() => command(ENCODER, 0, 200), RangeError);
  assert.throws(() => command(KEY, 256), RangeError);
});

test("the console finds the command word only in a firmware with the runtime's keys", () => {
  assert.equal(remoteMailbox(image(true)), MAILBOX);
  assert.equal(remoteMailbox(image(false)), null);
  assert.equal(remoteMailbox(new Uint8Array(0x1000)), null);
});

test("the stub is what the assembler makes of it, and the command line tool sends the same words", () => {
  const words = stub(MAILBOX, 0xa5000901);
  const source = `
    push {r4, r5, r6, lr}
    ldr r4, =${MAILBOX}
    ldr r5, [r4, #8]
    ldr r0, =${0xa5000901}
    str r0, [r4]
    mov r6, #50
wait:
    mov r0, #10
    ldr r12, =0xC0000B78
    blx r12
    ldr r0, [r4, #8]
    cmp r0, r5
    bne out
    subs r6, r6, #1
    bne wait
out:
    mov r0, #1
    pop {r4, r5, r6, pc}
.pool`;
  const run = spawnSync("python3", ["-c", "import sys, json, struct; sys.path.insert(0, 'tools/patch'); from arm import assemble; b = assemble(sys.stdin.read(), origin=0xC1000000).bytes; print(json.dumps(list(struct.unpack('<%dI' % (len(b) // 4), b))))"], { cwd: root, input: source, encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(words, JSON.parse(run.stdout));
  const tool = readFileSync(`${root}tools/device/remote_press.py`, "utf8").match(/words = \[([^\]]+)\]/)[1];
  const listed = tool.split(",").map(w => w.trim()).filter(w => /^0x/i.test(w)).map(Number);
  assert.deepEqual(listed, words.slice(0, 16));
});

test("KORG.press runs the stub through exec with the runtime's keys and uses the panel without them", async () => {
  for (const signed of [true, false]) {
    const bytes = image(signed);
    const port = {};
    const applied = [];
    const pressed = [];
    const blockers = [];
    const session = { port, firmware: {}, firmwareBytes: bytes, apply: async edit => { applied.push(edit); return { ok: true }; } };
    const korg = makeKorg({ session: () => session, emulator: { port, baseFirmware: bytes, button: async i => { pressed.push(i); } } },
      { hooks: { press: why => blockers.push(why) } });
    assert.equal(await korg.press("menu"), "menu gedrückt");
    if (signed) {
      assert.equal(applied.length, 1);
      assert.equal(applied[0].kind, "exec");
      assert.deepEqual(Array.from(new Uint32Array(applied[0].code.buffer)).slice(-3, -1), [MAILBOX, 0xa5000901]);
      assert.deepEqual(pressed, []);
      assert.deepEqual(blockers, [], "a key through exec can be sent to the device");
      assert.equal(await korg.turn(-2), "um -2 gedreht");
      assert.equal(applied[1].code.length, 76);
    } else {
      assert.deepEqual(applied, []);
      assert.deepEqual(pressed, [0x09]);
      assert.equal(blockers.length, 1, "a panel press stays in the emulator");
      await assert.rejects(korg.turn(1), /BLECH-Satz/);
    }
  }
});
