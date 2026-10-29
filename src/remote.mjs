/**
 * The device from the computer: KORG.press, KORG.turn, KORG.knob, KORG.pad, KORG.touch and KORG.testMode on a firmware
 * with the BLECH runtime.
 *
 * The runtime (tools/patch/script_remote.s) takes a command word from the work area of its card loader in the frame
 * hook and puts a panel message into the firmware's queue of panel messages, so the firmware takes it as one from the
 * panel. The console only leaves the word (and the message) there, through a stub run by KORG.exec; the stub then waits
 * until the runtime counted the command done, so a second command never overwrites a first one. The emulator and the
 * device get the same stub. (measure:2026-10-22/tasten-vom-rechner, measure:2026-10-29/test-modus-fernsteuerung)
 */
import { ramToFile } from "./map/address.mjs";
import { BUTTONS, ENCODERS, KNOBS, KNOB_MAX, PADS, TOUCH_BUTTON, TOUCHPAD_MAX } from "../data/panel.mjs";

/**
 * Where script_remote.s puts its signature, "REMT", then the command word's address: the runtime's code area
 * (tools/patch/script_hooks.py, MORE3_START), and the second code area that held it up to 1.3.7.
 */
const CODES = [{ from: 0xc0150300, to: 0xc0170000 }, { from: 0xc018d000, to: 0xc018ff00 }];
const SIGN = 0x544d4552;
/** "RMT2" behind the command word's address: a runtime that takes whole panel messages and has the test mode. */
const SIGN2 = 0x32544d52;
const MARK = 0xa5000000;
export const KEY = 1;
export const ENCODER = 2;
export const MESSAGE = 3;
export const TEST = 4;
export const RELEASE = 5;
/** The operating system's sleep (ms) of the Sampler (tools/patch/script_menu.s, OS_WAIT); a 1.3.8 runtime names its own. */
const OS_WAIT = 0xc0000b78;
/** How long the stub waits for the runtime: 50 times 10 ms. A key takes two frames of 40 ms. */
const TRIES = 50;
const LAST_KEY = Math.max(TOUCH_BUTTON, ...BUTTONS.map(b => b.index));

/**
 * Where the runtime's remote lives in a VSB: { mailbox, message, testMode, osWait } (message and testMode null in a runtime
 * up to 1.3.7, which only takes keys and the dial), or null without the runtime's keys.
 */
export function remoteInfo(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
  for (const code of CODES) {
    const from = ramToFile(code.from);
    const to = Math.min(ramToFile(code.to), bytes.length - 8);
    if (from < 0 || to <= from) continue;
    for (let at = from; at < to; at += 4) {
      if (view.getUint32(at, true) !== SIGN) continue;
      const full = at + 24 <= bytes.length && view.getUint32(at + 8, true) === SIGN2;
      return {
        mailbox: view.getUint32(at + 4, true), message: full ? view.getUint32(at + 12, true) : null,
        testMode: full ? view.getUint32(at + 16, true) : null, osWait: full ? view.getUint32(at + 20, true) : OS_WAIT,
      };
    }
  }
  return null;
}

/** The address of the command word in a VSB with the runtime's keys, or null. */
export const remoteMailbox = bytes => remoteInfo(bytes)?.mailbox ?? null;

const inRange = (value, min, max, what) => {
  if (!Number.isInteger(value) || value < min || value > max) throw new RangeError(`${what} ${min} bis ${max}`);
  return value;
};

/**
 * Panel messages (type, four data bytes) as the panel sends them (data/panel.mjs): a key down or up, a knob to a value,
 * a pad pressed with a velocity (0: let go), the touchpad at x, y (0 to 1023; touching is the key 0x22).
 */
export const panel = {
  key: (index, down) => [0, inRange(index, 0, LAST_KEY, "Taste"), down ? 1 : 0, 0, 0],
  knob: (index, value) => [2, inRange(index, 0, KNOBS.length - 1, "Regler"), 0, inRange(value, 0, KNOB_MAX, "Reglerwert"), 0],
  pad: (index, velocity) => [4, inRange(index, 0, PADS.length - 1, "Pad"), 0, inRange(velocity, 0, 127, "Anschlag"), velocity ? 1 : 0],
  touch: (x, y) => [5, inRange(x, 0, TOUCHPAD_MAX, "Touchpad x") >> 8, x & 0xff, inRange(y, 0, TOUCHPAD_MAX, "Touchpad y") >> 8, y & 0xff],
};

/**
 * The command word: a key (index), an encoder (index) turned by `value` (-128 to 127), the message, the test mode (value
 * 0 or 1), letting go of everything held. Out of range is refused here, before anything goes to the device.
 */
export function command(kind, index = 0, value = 0) {
  if (kind === KEY) inRange(index, 0, LAST_KEY, "Taste");
  else if (kind === ENCODER) { inRange(index, 0, ENCODERS.length - 1, "Drehgeber"); inRange(value, -128, 127, "Drehen um"); }
  else if (kind === TEST) inRange(value, 0, 1, "Test-Modus");
  else if (kind !== MESSAGE && kind !== RELEASE) throw new RangeError(`kein Befehl ${kind}`);
  if (kind !== KEY && kind !== ENCODER && index !== 0) throw new RangeError("dieser Befehl hat keinen Index");
  return (MARK | (value & 0xff) << 16 | index << 8 | kind) >>> 0;
}

/**
 * The stub for KORG.exec: note the done counter, write the command word, sleep 10 ms until the counter moved (at most
 * TRIES times). It returns 1 when the runtime took the command; else it takes the word back and returns 0, and EXEC
 * reports the failure. Assembled with tools/patch/arm.py; test/remote.test.mjs holds it against the assembler.
 */
export function stub(mailbox, word, osWait = OS_WAIT) {
  return [
    0xe92d4070, // push {r4, r5, r6, lr}
    0xe59f4040, // ldr r4, =mailbox
    0xe5945008, // ldr r5, [r4, #8]      done counter before
    0xe59f003c, // ldr r0, =word
    0xe5840000, // str r0, [r4]
    ...WAIT.map(w => w ?? 0xe59fc030),
    mailbox >>> 0, word >>> 0, osWait >>> 0,
  ];
}

/** The wait of both stubs: up to TRIES times 10 ms for the done counter, then 1, or 0 with the word taken back. */
const WAIT = [
  (0xe3a06000 | TRIES) >>> 0, // mov r6, #TRIES
  0xe3a0000a, // wait: mov r0, #10
  null, // ldr r12, =OS_WAIT (pc relative, differs between the stubs)
  0xe12fff3c, // blx r12
  0xe5940008, // ldr r0, [r4, #8]
  0xe1500005, // cmp r0, r5
  0x1a000004, // bne out
  0xe2566001, // subs r6, r6, #1
  0x1afffff7, // bne wait
  0xe3a00000, // mov r0, #0
  0xe5840000, // str r0, [r4]          the word back: nothing runs it later
  0xe8bd8070, // pop {r4, r5, r6, pc}
  0xe3a00001, // out: mov r0, #1
  0xe8bd8070, // pop {r4, r5, r6, pc}
];

/**
 * The stub for a whole panel message: as stub(), and before the command word the message's 8 bytes at `at` (the
 * runtime's RM_MSG_AT). Assembled with tools/patch/arm.py; test/remote.test.mjs holds it against the assembler.
 */
export function messageStub(mailbox, at, message, osWait = OS_WAIT) {
  const bytes = new Uint8Array(8);
  bytes.set(message.slice(0, 5));
  const view = new DataView(bytes.buffer);
  return [
    0xe92d4070, // push {r4, r5, r6, lr}
    0xe59f4050, // ldr r4, =mailbox
    0xe5945008, // ldr r5, [r4, #8]      done counter before
    0xe59f104c, // ldr r1, =at
    0xe59f204c, // ldr r2, =message, first word
    0xe59f304c, // ldr r3, =message, second word
    0xe881000c, // stmia r1, {r2, r3}
    0xe59f0048, // ldr r0, =command word
    0xe5840000, // str r0, [r4]
    ...WAIT.map(w => w ?? 0xe59fc03c),
    mailbox >>> 0, at >>> 0, view.getUint32(0, true), view.getUint32(4, true), command(MESSAGE), osWait >>> 0,
  ];
}
