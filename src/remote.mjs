/**
 * Keys from the computer: KORG.press and KORG.turn on a firmware with the BLECH runtime.
 *
 * The runtime (tools/patch/script_remote.s) takes a command word from the work area of its card loader in the frame
 * hook, in the UI task, and goes through the firmware's key and encoder handlers, as korg.play does. The console only
 * leaves the word there, through a stub run by KORG.exec; the stub then waits until the runtime counted the command
 * done, so a second press never overwrites a first one. The emulator and the device get the same stub.
 * (measure:2026-10-22/tasten-vom-rechner)
 */
import { ramToFile } from "./map/address.mjs";

/**
 * Where script_remote.s puts its signature, "REMT", then the command word's address: the runtime's code area
 * (tools/patch/script_hooks.py, MORE3_START), and the second code area that held it up to 1.3.7.
 */
const CODES = [{ from: 0xc0150300, to: 0xc0170000 }, { from: 0xc018d000, to: 0xc018ff00 }];
const SIGN = 0x544d4552;
const MARK = 0xa5000000;
export const KEY = 1;
export const ENCODER = 2;
/** The operating system's sleep (ms), as the runtime's power key code calls it (tools/patch/script_menu.s, OS_WAIT). */
const OS_WAIT = 0xc0000b78;
/** How long the stub waits for the runtime: 50 times 10 ms. A key takes two frames of 40 ms. */
const TRIES = 50;

/** The address of the command word in a VSB with the runtime's keys, or null. */
export function remoteMailbox(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
  for (const code of CODES) {
    const from = ramToFile(code.from);
    const to = Math.min(ramToFile(code.to), bytes.length - 8);
    if (from < 0 || to <= from) continue;
    for (let at = from; at < to; at += 4) {
      if (view.getUint32(at, true) === SIGN) return view.getUint32(at + 4, true);
    }
  }
  return null;
}

/** The command word: a key (index) or the encoder `index` turned by `value` (signed, -128 to 127). */
export function command(kind, index, value = 0) {
  if (!Number.isInteger(index) || index < 0 || index > 0xff) throw new RangeError("index 0 to 255");
  if (!Number.isInteger(value) || value < -128 || value > 127) throw new RangeError("Drehen um -128 bis 127");
  return (MARK | (value & 0xff) << 16 | index << 8 | kind) >>> 0;
}

/**
 * The stub for KORG.exec: note the done counter, write the command word, sleep 10 ms until the counter moved (at most
 * TRIES times), return 1. Assembled with tools/patch/arm.py; test/remote.test.mjs holds it against the assembler.
 */
export function stub(mailbox, word) {
  return [
    0xe92d4070, // push {r4, r5, r6, lr}
    0xe59f4034, // ldr r4, =mailbox
    0xe5945008, // ldr r5, [r4, #8]      done counter before
    0xe59f0030, // ldr r0, =word
    0xe5840000, // str r0, [r4]
    (0xe3a06000 | TRIES) >>> 0, // mov r6, #TRIES
    0xe3a0000a, // mov r0, #10
    0xe59fc024, // ldr r12, =OS_WAIT
    0xe12fff3c, // blx r12
    0xe5940008, // ldr r0, [r4, #8]
    0xe1500005, // cmp r0, r5
    0x1a000001, // bne out
    0xe2566001, // subs r6, r6, #1
    0x1afffff7, // bne wait
    0xe3a00001, // out: mov r0, #1
    0xe8bd8070, // pop {r4, r5, r6, pc}
    mailbox >>> 0, word >>> 0, OS_WAIT,
  ];
}
