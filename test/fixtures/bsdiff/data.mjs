// The made-up inputs of make.py, built again in JS so the tests need no second copy of them in the repository.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

export const SIZE = 0x200100;
export const sha = bytes => createHash("sha256").update(bytes).digest("hex");
export const expected = JSON.parse(readFileSync(new URL("./expected.json", import.meta.url), "utf8"));
export const fixture = path => new Uint8Array(readFileSync(new URL(path, import.meta.url)));

export function noise(n, seed, alphabet = 256) {
  const out = new Uint8Array(n);
  let x = seed >>> 0;
  for (let i = 0; i < n; i++) {
    x = (x ^ (x << 13)) >>> 0;
    x = (x ^ (x >>> 17)) >>> 0;
    x = (x ^ (x << 5)) >>> 0;
    out[i] = (x >>> 8) % alphabet;
  }
  return out;
}

export function edited(old) {
  const out = old.slice();
  out.set(noise(64, 3), 100_000);
  out.set([1, 2, 3], 400_000);
  out.set(old.subarray(1_500_000, 1_505_000), 900_000);
  out.set(noise(10, 9), 2_000_000);
  return out;
}

export const oldFile = () => noise(SIZE, 1);

/** The made-up Hacktribe firmware of test/helpers.mjs and the stand-in for Korg's original that make.py patched it from. */
export async function fakeFirmware() {
  const { makeFirmware } = await import("../../helpers.mjs");
  const hacktribe = await makeFirmware();
  const original = hacktribe.slice();
  original.set(noise(64, 5), 0x1F0000);
  original[0x1F8000] = 0x77;
  return { original, hacktribe };
}
