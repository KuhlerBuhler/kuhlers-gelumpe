import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { check, fingerprints } from "../tools/korg-guard.mjs";

// No Korg data here: the headers are typed out, the "known" data is random bytes made up in the test.
const random = (n, seed) => {
  const parts = [];
  for (let i = 0; parts.length * 32 < n; i++) parts.push(createHash("sha256").update(`${seed}:${i}`).digest());
  return Buffer.concat(parts).subarray(0, n);
};

test("Korg file headers and names are refused", () => {
  const vsb = Buffer.concat([Buffer.from("KORG SYSTEM FILE"), Buffer.alloc(64)]);
  assert.ok(check("x.bin", vsb, new Set()).some(r => /system file/.test(r)));
  const pat = Buffer.alloc(64); pat.write("KORG", 0); pat.write("e2sampler", 16);
  assert.ok(check("a.dat", pat, new Set()).some(r => /pattern/.test(r)));
  assert.ok(check("b", Buffer.from("e2s sample all\x1a\0"), new Set()).length);
  assert.ok(check("SYSTEM.VSB", Buffer.from("hello"), new Set()).length);
  assert.deepEqual(check("README.md", Buffer.from("# hello"), new Set()), []);
});

test("a slice of known data is found at any offset, also as hex text, and unrelated data is not", () => {
  const data = random(200_000, "known");
  const known = fingerprints(data);
  assert.ok(known.size > 50);
  const slice = Buffer.concat([Buffer.from("abc"), data.subarray(12_345, 12_345 + 20_000)]);
  assert.ok(check("slice.bin", slice, known).length, "binary slice");
  const hex = Buffer.from(`{"x":"${data.subarray(50_001, 50_001 + 20_000).toString("hex")}"}`);
  assert.ok(check("x.json", hex, known).some(r => /hex/.test(r)), "hex run");
  assert.deepEqual(check("other.bin", random(300_000, "other"), known), []);
  assert.deepEqual(check("ff.bin", Buffer.alloc(100_000, 0xff), known), [], "erased flash is no fingerprint");
});

test("the tracked files of this repository pass the guard", () => {
  const files = execFileSync("git", ["ls-files"], { encoding: "utf8" }).split("\n").filter(Boolean);
  execFileSync(process.execPath, ["tools/korg-guard.mjs", ...files], { stdio: "pipe" });
});
