/**
 * A firmware of our own and a patch set for it, for the tests of the patch file and the bsdiff.
 * Nothing here is Korg's: the "firmware" is the helpers' image with filler and a pseudo-random
 * stretch the code patch copies from.
 */
import { splashPatch, PATCH_FORMAT, SPLASH_W, SPLASH_H } from "../../src/patch.mjs";
import { sha256 } from "../../src/firmware.mjs";
import { makeFirmware } from "../helpers.mjs";

export const CODE = 0x1a2200;
export const COPY_TO = 0x1a2100;
export const COPY_FROM = 0x1a3000;

export async function fixture() {
  const vsb = await makeFirmware();
  vsb.fill(0xff, COPY_TO, COPY_TO + 0x200);
  let x = 12345;
  for (let i = 0; i < 256; i++) { x = (x * 1103515245 + 12345) >>> 0; vsb[COPY_FROM + i] = x >>> 24; }
  const hash = (at, n) => sha256(vsb.subarray(at, at + n));
  const checker = new Uint8Array(SPLASH_W * SPLASH_H).map((_, i) => ((i % SPLASH_W) + (i >> 7)) & 1);
  const code = {
    format: PATCH_FORMAT, version: 1, id: "code", name: "Code",
    changes: [
      { file: CODE, bytes: "0040a0e10150a0e1e12fff1e00000000", expect: await hash(CODE, 16), note: "our code" },
      {
        file: COPY_TO, copy: { file: COPY_FROM, length: 64, expect: await hash(COPY_FROM, 64) },
        over: [{ at: 8, bytes: "aabbccdd" }, { at: 40, bytes: "11" }], expect: await hash(COPY_TO, 64),
      },
    ],
    hooks: [{ site: "0xC002ADAC", kind: "call", chain: "start", position: "after", swallow: false }],
    startPhase: [{ file: CODE, length: 16, why: "test" }],
  };
  return { vsb, patches: [code, splashPatch(checker)] };
}
