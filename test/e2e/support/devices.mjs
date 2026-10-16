/** Synthetic profile for the generated browser-test image. */
import { sha256 } from "/src/firmware.mjs";
export default [{ version: [2, 2], label: "simulation", fingerprints: [
  { addr: 0xc0000040, length: 16, sha256: await sha256(new Uint8Array(16)) },
] }];
