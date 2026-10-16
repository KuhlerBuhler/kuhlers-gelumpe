#!/usr/bin/env node
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { buildOf } from "../../src/firmware.mjs";
import { readImages } from "./blech_theme.mjs";

export function buildSplashPatch(vsb, art) {
  if (buildOf(vsb) !== "synth") throw new Error("the splash requires the synth firmware");
  const image = readImages(vsb)[13];
  if (image.w !== 128 || image.h !== 64 || art.length !== 1024) throw new Error("the start image must be 128 by 64 pixels, 1024 bytes");
  const file = image.data - 0xC0000000 + 0x100;
  if (file < 0x100 || file + 1024 > vsb.length) throw new Error("the start image lies outside the VSB");
  return {
    format: "gelumpe-patch", version: 1, id: "splash", name: "Blech Startbild", builds: ["synth"],
    changes: [{ file, bytes: Buffer.from(art).toString("hex"), expect: createHash("sha256").update(vsb.subarray(file, file + 1024)).digest("hex") }],
    startPhase: [{ file, length: 1024, why: "the firmware draws image 13 during startup; only its bitmap changes" }], ram: [],
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const option = name => process.argv[process.argv.indexOf(name) + 1];
  if (!process.argv.includes("--vsb") || !process.argv.includes("--out")) throw new Error("usage: splash_synth.mjs --vsb SYSTEM.VSB --out patch.json");
  const art = readFileSync(new URL("../../assets/blechy/splash.bin", import.meta.url));
  const patch = buildSplashPatch(new Uint8Array(readFileSync(option("--vsb"))), art);
  writeFileSync(option("--out"), `${JSON.stringify(patch, null, 1)}\n`);
}
