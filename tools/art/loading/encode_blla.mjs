#!/usr/bin/env node
/**
 * Encodes pictures into a loading animation file (src/loading-anim.mjs, docs/hintergrund/ladeanimation.md) for the
 * asset tool: reads { progress: [hex], loop: [hex], loopFrom } as JSON on stdin and prints the file as hex.
 *
 *   node tools/art/loading/encode_blla.mjs < frames.json
 */
import { readFileSync } from "node:fs";
import { encodeAnimation } from "../../../src/loading-anim.mjs";

const input = JSON.parse(readFileSync(0, "utf8"));
const frame = hex => new Uint8Array(Buffer.from(hex, "hex"));
const { bytes } = encodeAnimation({ progress: input.progress.map(frame), loop: (input.loop ?? []).map(frame), loopFrom: input.loopFrom ?? 0 });
process.stdout.write(`${Buffer.from(bytes).toString("hex")}\n`);
