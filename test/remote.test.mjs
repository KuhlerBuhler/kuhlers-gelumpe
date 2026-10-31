import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { remoteMailbox, remoteInfo, command, stub, messageStub, panel, KEY, ENCODER, MESSAGE, TEST, RELEASE } from "../src/remote.mjs";
import { makeKorg } from "../src/korg.mjs";
import { ramToFile } from "../src/map/address.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const MAILBOX = 0xc01f7fc0;

const MESSAGE_AT = 0xc01f7fa0;
const TEST_FLAG = 0xc015b7f0;
const SYNTH_WAIT = 0xc00009a0;
const WAIT_TAIL = `
    mov r6, #50
wait:
    mov r0, #10
    ldr r12, =OS_WAIT_AT
    blx r12
    ldr r0, [r4, #8]
    cmp r0, r5
    bne out
    subs r6, r6, #1
    bne wait
    mov r0, #0
    str r0, [r4]
    pop {r4, r5, r6, pc}
out:
    mov r0, #1
    pop {r4, r5, r6, pc}
.pool`;

/**
 * A firmware file long enough for the runtime's code area, with the signature of tools/patch/script_remote.s or without;
 * `full` adds "RMT2", the message and the test mode of 1.3.8.
 */
function image(signed, at = 0xc0157b18, full = false) {
  const bytes = new Uint8Array(ramToFile(0xc0190000)).fill(0xff);
  if (signed) {
    const view = new DataView(bytes.buffer);
    view.setUint32(ramToFile(at), 0x544d4552, true);
    view.setUint32(ramToFile(at + 4), MAILBOX, true);
    if (full) {
      view.setUint32(ramToFile(at + 8), 0x32544d52, true);
      view.setUint32(ramToFile(at + 12), MESSAGE_AT, true);
      view.setUint32(ramToFile(at + 16), TEST_FLAG, true);
      view.setUint32(ramToFile(at + 20), SYNTH_WAIT, true);
    }
  }
  return bytes;
}

const assemble = source => {
  const run = spawnSync("python3", ["-c", "import sys, json, struct; sys.path.insert(0, 'tools/patch'); from arm import assemble; b = assemble(sys.stdin.read(), origin=0xC1000000).bytes; print(json.dumps(list(struct.unpack('<%dI' % (len(b) // 4), b))))"], { cwd: root, input: source, encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  return JSON.parse(run.stdout);
};

test("a key and a turn of the dial become marked command words, and bad values are refused", () => {
  assert.equal(command(KEY, 0x09), 0xa5000901);
  assert.equal(command(ENCODER, 0, -1), 0xa5ff0002);
  assert.equal(command(ENCODER, 0, 3), 0xa5030002);
  assert.throws(() => command(ENCODER, 0, 200), RangeError);
  assert.throws(() => command(KEY, 256), RangeError);
});

test("the console finds the command word only in a firmware with the runtime's keys", () => {
  assert.equal(remoteMailbox(image(true)), MAILBOX);
  assert.equal(remoteMailbox(image(true, 0xc018eb18)), MAILBOX, "the second code area of a firmware up to 1.3.7");
  assert.equal(remoteMailbox(image(false)), null);
  assert.equal(remoteMailbox(new Uint8Array(0x1000)), null);
});

test("the stub is what the assembler makes of it, returns 0 when the runtime does not take it, and the command line tool sends the same words", () => {
  const words = stub(MAILBOX, 0xa5000901);
  assert.deepEqual(words, assemble(`
    push {r4, r5, r6, lr}
    ldr r4, =${MAILBOX}
    ldr r5, [r4, #8]
    ldr r0, =${0xa5000901}
    str r0, [r4]${WAIT_TAIL.replace("OS_WAIT_AT", "0xC0000B78")}`));
  assert.equal(stub(MAILBOX, 1, SYNTH_WAIT).at(-1), SYNTH_WAIT);
  const tool = readFileSync(`${root}tools/device/remote_press.py`, "utf8");
  const wait = tool.match(/WAIT = \[([^\]]+)\]/)[1].split(",").map(w => w.trim()).map(w => (w === "None" ? null : Number(w)));
  const head = tool.match(/def stub[\s\S]*?words = \[([^*]+)\*/)[1].split(",").map(w => w.trim()).filter(w => /^0x/i.test(w)).map(Number);
  assert.deepEqual([...head, ...wait.map(w => w ?? 0xe59fc030)], words.slice(0, 19));
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
      assert.equal(applied[1].code.length, 88);
    } else {
      assert.deepEqual(applied, []);
      assert.deepEqual(pressed, [0x09]);
      assert.equal(blockers.length, 1, "a panel press stays in the emulator");
      await assert.rejects(korg.turn(1), /BLECH-Satz/);
    }
  }
});

test("panel messages, the test mode word and where a 1.3.8 runtime keeps them", () => {
  assert.deepEqual(panel.knob(0, 200), [2, 0, 0, 200, 0]);
  assert.deepEqual(panel.pad(4, 100), [4, 4, 0, 100, 1]);
  assert.deepEqual(panel.pad(4, 0), [4, 4, 0, 0, 0]);
  assert.deepEqual(panel.touch(400, 300), [5, 1, 144, 1, 44]);
  assert.deepEqual(panel.key(0x0a, true), [0, 0x0a, 1, 0, 0]);
  assert.equal(command(TEST, 0, 1), 0xa5010004);
  assert.equal(command(MESSAGE, 0), 0xa5000003);
  assert.deepEqual(remoteInfo(image(true, 0xc0159fe8, true)), { mailbox: MAILBOX, message: MESSAGE_AT, testMode: TEST_FLAG, osWait: SYNTH_WAIT });
  assert.deepEqual(remoteInfo(image(true)), { mailbox: MAILBOX, message: null, testMode: null, osWait: 0xc0000b78 }, "a runtime up to 1.3.7: keys and the dial only");
  assert.equal(remoteInfo(image(false)), null);
});

test("the message stub is what the assembler makes of it, and the command line tool sends the same words", () => {
  const words = messageStub(MAILBOX, MESSAGE_AT, [4, 4, 0, 100, 1]);
  assert.deepEqual(words, assemble(`
    push {r4, r5, r6, lr}
    ldr r4, =${MAILBOX}
    ldr r5, [r4, #8]
    ldr r1, =${MESSAGE_AT}
    ldr r2, =${0x64000404}
    ldr r3, =${0x00000001}
    stmia r1, {r2, r3}
    ldr r0, =${0xa5000003}
    str r0, [r4]${WAIT_TAIL.replace("OS_WAIT_AT", "0xC0000B78")}`));
  const tool = readFileSync(`${root}tools/device/remote_press.py`, "utf8");
  const wait = tool.match(/WAIT = \[([^\]]+)\]/)[1].split(",").map(w => w.trim()).map(w => (w === "None" ? null : Number(w)));
  const head = tool.match(/def message_stub[\s\S]*?words = \[([^*]+)\*/)[1].split(",").map(w => w.trim()).filter(w => /^0x/i.test(w)).map(Number);
  assert.deepEqual([...head, ...wait.map(w => w ?? 0xe59fc03c)], words.slice(0, 23));
});

test("keys, encoders, pads, knobs, the touchpad and turns out of range are refused before anything is sent", () => {
  for (const bad of [() => command(KEY, 0x23), () => command(ENCODER, 5, 1), () => command(ENCODER, 0, 128), () => command(ENCODER, 0, -129),
    () => command(TEST, 0, 2), () => command(MESSAGE, 3), () => command(9), () => panel.pad(16, 100), () => panel.pad(0, 128),
    () => panel.knob(11, 1), () => panel.knob(0, 256), () => panel.touch(1024, 0), () => panel.key(0x23, true)]) assert.throws(bad, RangeError);
  assert.equal(command(RELEASE), 0xa5000005);
  const run = spawnSync("python3", ["-c", `import sys; sys.path.insert(0, "tools/device")
import remote_press as r
names = r.panel_names()
for step in ["+128", "-129", "cutoff+200", "pad17", "pad1:200", "level=256", "touch=1024,1", "nokey", "nokey:down", "bogus=3"]:
    try:
        r.command(step, names)
    except SystemExit:
        continue
    raise AssertionError(step)
print("refused")`], { cwd: root, encoding: "utf8" });
  assert.equal(run.stdout.trim(), "refused", run.stderr);
});

test("KORG.knob, pad, touch, hold and testMode go through exec on a 1.3.8 runtime and are refused on an older one", async () => {
  const session = bytes => {
    const applied = [];
    const s = { port: {}, firmware: {}, firmwareBytes: bytes, apply: async edit => { applied.push(edit); return { ok: true }; } };
    return { applied, korg: makeKorg({ session: () => s, emulator: { port: s.port, baseFirmware: bytes, button: async () => {} } }, { hooks: {} }) };
  };
  const { applied, korg } = session(image(true, 0xc0159fe8, true));
  const words = edit => Array.from(new Uint32Array(edit.code.buffer));
  assert.equal(await korg.knob("level", 200), "level auf 200");
  assert.deepEqual(words(applied[0]).slice(-6, -1), [MAILBOX, MESSAGE_AT, 0xc8000002, 0, 0xa5000003]);
  await korg.pad(5, { velocity: 64 });
  assert.deepEqual(words(applied[1]).slice(-4, -2), [0x40000404, 1]);
  assert.deepEqual(words(applied[2]).slice(-4, -2), [0x00000404, 0], "struck: let go again");
  await korg.touch(400, 300);
  assert.equal(applied.length, 6, "touch: key 0x22 down, the place, key 0x22 up");
  await korg.hold("shift", true);
  assert.deepEqual(words(applied[6]).slice(-4, -2), [0x00010a00, 0]);
  assert.equal(await korg.turn(2, "cutoff"), "um 2 gedreht");
  assert.deepEqual(words(applied[7]).slice(-3, -1), [MAILBOX, 0xa5020202]);
  assert.match(await korg.testMode(true), /Test-Modus an/);
  assert.deepEqual(words(applied[8]).slice(-3, -1), [MAILBOX, 0xa5010004]);
  await assert.rejects(korg.knob("level", 300), RangeError);
  await assert.rejects(korg.knob("nope", 1), /nope/);
  assert.equal(words(applied[8]).at(-1), SYNTH_WAIT, "the sleep the runtime names");
  await assert.rejects(korg.turn(1, 5), /Drehgeber/);
  await assert.rejects(korg.press(0x40), RangeError);
  // the runtime does not take a command (EXEC answers the stub's 0): the console says so, and a held pad is let go
  const failing = image(true, 0xc0159fe8, true);
  const tried = [];
  const s2 = { port: {}, firmware: {}, firmwareBytes: failing, apply: async edit => { tried.push(edit); return tried.length === 2 ? { ok: false, error: { message: "EXEC lieferte 0" } } : { ok: true }; } };
  const korg2 = makeKorg({ session: () => s2, emulator: { port: s2.port, baseFirmware: failing, button: async () => {} } }, { hooks: {} });
  await assert.rejects(korg2.pad(3), /nicht genommen.*EXEC lieferte 0/);
  assert.deepEqual(words(tried[2]).slice(-3, -1), [MAILBOX, 0xa5000005], "after the failure: let go of everything");
  assert.equal(await korg2.release(), "alles losgelassen");
  const old = session(image(true));
  await assert.rejects(old.korg.knob("level", 1), /1\.3\.8/);
  await assert.rejects(old.korg.testMode(true), /1\.3\.8/);
  assert.equal(old.applied.length, 0);
});
