#!/usr/bin/env node
/**
 * Keeps Korg's data out of the repository: firmware, factory patterns, samples.
 *
 *   node tools/korg-guard.mjs FILE...                      check files, exit 1 on a hit
 *   node tools/korg-guard.mjs --build OUT SOURCE... [--except FILE...]
 *                                                          build the fingerprint file from your own Korg files; windows that
 *                                                          also occur in FILE (our own binaries, which share the C library
 *                                                          with Korg's firmware) are left out
 *
 * A hit is any of: a Korg file header (system file, pattern file, sample collection, a WAV with Korg's
 * sample chunk), a Korg file name, or enough fingerprints of Korg data inside the bytes, also when the
 * bytes sit in the file as hex or base64 text. The fingerprints are content defined: of every 64-byte window
 * whose rolling hash hits a fixed pattern, only a truncated SHA-256 is kept. Nothing of the data itself is
 * stored, and a slice cut out at any offset still carries the windows it had.
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";
import { fileURLToPath } from "node:url";

const WINDOW = 64;
const MASK = 0x3ff;            // about one window in 1024 is kept
const MIN_HITS = 3;            // fewer shared windows than this is chance
const FINGERPRINTS = fileURLToPath(new URL("../data/korg-fingerprints.bin", import.meta.url));
const BASE = 257;
const MOD = 1_000_000_007;

const HEADERS = [
  { what: "Korg system file (firmware)", test: b => ascii(b, 0, 16) === "KORG SYSTEM FILE" },
  { what: "Korg pattern file", test: b => ascii(b, 0, 4) === "KORG" && ascii(b, 16, 9) === "e2sampler" },
  { what: "Korg sample collection (e2sSample.all)", test: b => ascii(b, 0, 14) === "e2s sample all" },
  { what: "WAV with Korg's sample chunk", test: b => ascii(b, 0, 4) === "RIFF" && ascii(b, 8, 4) === "WAVE" && indexOf(b, "esli") >= 0 && indexOf(b, "korg") >= 0 },
];
const NAMES = [/\.vsb$/i, /\.e2sallpat$/i, /\.e2spat$/i, /e2ssample\.all$/i];

function ascii(b, at, n) {
  return b.length >= at + n ? b.subarray(at, at + n).toString("latin1") : "";
}

function indexOf(b, text) {
  return b.indexOf(Buffer.from(text, "latin1"));
}

/** The kept windows of `bytes` as 8-byte hex keys. Windows of one repeated byte (erased flash, silence) are skipped. */
export function fingerprints(bytes) {
  const out = new Set();
  if (bytes.length < WINDOW) return out;
  let power = 1;
  for (let i = 0; i < WINDOW - 1; i++) power = (power * BASE) % MOD;
  let h = 0;
  for (let i = 0; i < WINDOW; i++) h = (h * BASE + bytes[i]) % MOD;
  for (let i = 0; ; i++) {
    if ((h & MASK) === 0) {
      const win = bytes.subarray(i, i + WINDOW);
      if (!win.every(v => v === win[0])) out.add(createHash("sha256").update(win).digest("hex").slice(0, 16));
    }
    if (i + WINDOW >= bytes.length) break;
    h = (h - (bytes[i] * power) % MOD + MOD) % MOD;
    h = (h * BASE + bytes[i + WINDOW]) % MOD;
  }
  return out;
}

/** Binary runs hidden in text: long hex and base64 strings, decoded. */
function decodedRuns(bytes) {
  const text = bytes.toString("latin1");
  const runs = [];
  for (const m of text.matchAll(/[0-9a-fA-F]{128,}/g)) runs.push(Buffer.from(m[0].length % 2 ? m[0].slice(1) : m[0], "hex"));
  for (const m of text.matchAll(/[A-Za-z0-9+/]{128,}={0,2}/g)) runs.push(Buffer.from(m[0], "base64"));
  return runs;
}

function loadKnown() {
  try {
    const raw = readFileSync(FINGERPRINTS);
    const known = new Set();
    for (let i = 0; i + 8 <= raw.length; i += 8) known.add(raw.subarray(i, i + 8).toString("hex"));
    return known;
  } catch {
    return new Set();
  }
}

/** The reasons `bytes` (named `name`) counts as Korg data; empty when it does not. */
export function check(name, bytes, known = loadKnown()) {
  const reasons = [];
  if (NAMES.some(r => r.test(basename(name)))) reasons.push(`file name ${basename(name)}`);
  for (const h of HEADERS) if (h.test(bytes)) reasons.push(h.what);
  if (known.size) {
    for (const part of [bytes, ...decodedRuns(bytes)]) {
      let hits = 0;
      for (const f of fingerprints(part)) if (known.has(f)) hits += 1;
      if (hits >= MIN_HITS) {
        reasons.push(`${hits} fingerprints of Korg data${part === bytes ? "" : " in a hex or base64 run"}`);
        break;
      }
    }
  }
  return reasons;
}

function main(args) {
  if (args[0] === "--build") {
    const cut = args.indexOf("--except");
    const [, out, ...sources] = cut < 0 ? args : args.slice(0, cut);
    const own = cut < 0 ? [] : args.slice(cut + 1);
    const all = new Set();
    for (const s of sources) for (const f of fingerprints(readFileSync(s))) all.add(f);
    for (const s of own) for (const f of fingerprints(readFileSync(s))) all.delete(f);
    writeFileSync(out, Buffer.concat([...all].sort().map(f => Buffer.from(f, "hex"))));
    console.log(`${all.size} fingerprints from ${sources.length} file(s) -> ${out}`);
    return 0;
  }
  const known = loadKnown();
  let bad = 0;
  for (const file of args) {
    let bytes;
    try { bytes = readFileSync(file); } catch { continue; }       // deleted in the change
    const reasons = check(file, bytes, known);
    if (reasons.length) {
      bad += 1;
      console.log(`${file}: ${reasons.join(", ")}`);
    }
  }
  if (bad) console.log(`\n${bad} file(s) look like Korg data. Korg's firmware, patterns and samples never go into this repository.`);
  return bad ? 1 : 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exit(main(process.argv.slice(2)));
