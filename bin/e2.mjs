#!/usr/bin/env node
/**
 * Command line front end.
 *
 *   e2 ls      <SYSTEM.VSB> [mfx|ifx]
 *   e2 show    <SYSTEM.VSB> <mfx|ifx> <slot>
 *   e2 lint    <SYSTEM.VSB> [mfx|ifx] [slot]
 *   e2 profile <SYSTEM.VSB>
 *   e2 selftest <SYSTEM.VSB>
 *
 * The firmware image is always yours and always stays where it is; nothing
 * here writes to it.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { VsbImage } from "../src/image.mjs";
import { readImage, readUnits } from "../src/node.mjs";
import { hex } from "../src/units.mjs";
import { buildProfile } from "../src/profile.mjs";
import { lint, worst, SEVERITY_ORDER } from "../src/rules.mjs";
import { SimDevice } from "../src/device.mjs";
import { syxEnc, syxDec, u32le } from "../src/bytes.mjs";
import { TABLE, RECORD_SIZE } from "../src/layout.mjs";

const PROFILE_PATH = ".e2/factory-profile.json";

const COLOUR = {
  fatal: "\x1b[1;31m", silent: "\x1b[35m", error: "\x1b[31m",
  warn: "\x1b[33m", note: "\x1b[90m", off: "\x1b[0m",
};
const paint = (severity, text) =>
  process.stdout.isTTY ? `${COLOUR[severity] || ""}${text}${COLOUR.off}` : text;

function usage(code = 1) {
  process.stderr.write(readFileSync(new URL("./usage.txt", import.meta.url), "utf8"));
  process.exit(code);
}

function loadProfile() {
  if (!existsSync(PROFILE_PATH)) return null;
  return JSON.parse(readFileSync(PROFILE_PATH, "utf8"));
}

function targets(image, kind, slot) {
  const kinds = kind ? [kind] : ["ifx", "mfx"];
  const out = [];
  for (const k of kinds) {
    if (slot) { out.push({ kind: k, slot: Number(slot), record: image.read(k, Number(slot)) }); continue; }
    for (const entry of image.list(k)) out.push({ kind: k, slot: entry.slot, record: entry.record });
  }
  return out;
}

const commands = {
  ls(path, kind) {
    const image = readImage(path);
    const units = readUnits();
    for (const k of kind ? [kind] : ["ifx", "mfx"]) {
      const rows = image.list(k);
      console.log(`\n${k.toUpperCase()}  ${rows.length} presets, menu shows ` +
        `${k === "mfx" ? image.mfxCount : image.ifxCount.value}`);
      for (const { slot, name, record } of rows) {
        const chain = record.stageNames
          .map(s => record.device(s))
          .filter(Boolean)
          .map(hex)
          .join(" -> ");
        console.log(`  ${String(slot).padStart(3)}  ${name.padEnd(16)} ${chain}`);
      }
    }
    if (!kind || kind === "ifx") {
      const menu = image.ifxCount;
      if (!menu.agreed) {
        console.log(paint("error",
          `\nthe insert menu length disagrees between its thirteen storage sites: ` +
          `counts ${menu.counts.join(",")} last ${menu.last.join(",")}`));
      }
    }
  },

  show(path, kind, slot) {
    if (!kind || !slot) usage();
    const image = readImage(path);
    const units = readUnits();
    const record = image.read(kind, Number(slot));
    console.log(JSON.stringify(record.describe(units), null, 2));
  },

  lint(path, kind, slot) {
    const image = readImage(path);
    const units = readUnits();
    const profile = loadProfile();
    if (!profile) {
      console.log(paint("note",
        `no factory profile yet, so value checks are skipped. Build one with:  e2 profile ${path}\n`));
    }

    const counts = Object.fromEntries(SEVERITY_ORDER.map(s => [s, 0]));
    let clean = 0;

    for (const t of targets(image, kind, slot)) {
      const findings = lint(t.record, { units, profile });
      if (!findings.length) { clean++; continue; }
      console.log(`\n${t.kind.toUpperCase()} ${t.slot}  ${t.record.name}`);
      for (const f of findings) {
        counts[f.severity]++;
        console.log(`  ${paint(f.severity, f.severity.padEnd(6))} ${f.where.padEnd(6)} ${f.message}`);
      }
    }

    const summary = SEVERITY_ORDER.filter(s => counts[s]).map(s => `${counts[s]} ${s}`).join(", ");
    console.log(`\n${clean} clean, ${summary || "nothing else found"}`);
    process.exitCode = counts.fatal || counts.silent || counts.error ? 1 : 0;
  },

  profile(path) {
    const image = readImage(path);
    const profile = buildProfile(image, readUnits());
    mkdirSync(".e2", { recursive: true });
    writeFileSync(PROFILE_PATH, JSON.stringify(profile, null, 1));
    const n = Object.keys(profile.params).length;
    const enums = Object.values(profile.params).filter(p => p.enum).length;
    console.log(`${PROFILE_PATH}: ${n} parameters from ${path}, ${enums} of them look like a list of choices`);
    console.log("It is derived from your firmware, so it is gitignored.");
  },

  /** Drive the simulated device the way the real tools do and report on it. */
  selftest(path) {
    const image = readImage(path);
    const units = readUnits();
    const dev = new SimDevice({ image: new VsbImage(image.bytes), channel: 7 });

    const request = (cmd, payload) =>
      dev.handle([0xf0, ...dev.head, cmd, ...syxEnc(payload), 0xf7]);

    const search = dev.handle([0xf0, 0x42, 0x50, 0x00, 0x00, 0xf7]);
    console.log(`device search -> global channel ${search[4]}`);

    const addr = image.slotOffset("mfx", 1);
    const ram = 0xc00b4f30;
    const reply = request(0x52, [...u32le(ram), ...u32le(RECORD_SIZE)]);
    const got = Uint8Array.from(syxDec(reply.slice(9, -1))).slice(0, RECORD_SIZE);
    const same = Buffer.compare(Buffer.from(got), Buffer.from(image.bytes.subarray(addr, addr + RECORD_SIZE))) === 0;
    console.log(`read MFX 1 over SysEx -> ${same ? "matches the image" : "DIFFERS from the image"}`);

    request(0x53, [...u32le(ram), ...u32le(4)]);
    dev.handle([0xf0, ...dev.head, 0x54, ...syxEnc([1, 2, 3, 4]), 0xf7]);
    const back = dev.peek(ram, 4);
    console.log(`write four bytes and read back -> ${[...back].join(",")}`);

    // Three ways to be refused, each of which the hardware answers with the
    // same silence: wrong global channel, an address outside the image, and
    // data sent without an address in front of it.
    dev.handle([0xf0, 0x42, 0x30, 0x00, 0x01, 0x24, 0x52, ...syxEnc([...u32le(ram), ...u32le(4)]), 0xf7]);
    request(0x52, [...u32le(0xc0400000), ...u32le(4)]);
    dev.handle([0xf0, ...dev.head, 0x54, ...syxEnc([1, 2, 3, 4]), 0xf7]);

    console.log("\nrefusals the real device would have answered with silence:");
    for (const f of dev.faults) console.log(`  ${f.code.padEnd(14)} ${f.message}`);
  },
};

const [, , name, ...args] = process.argv;
if (!name || !commands[name] || !args[0]) usage();
if (!existsSync(args[0])) {
  process.stderr.write(`no such file: ${args[0]}\n`);
  process.exit(1);
}
await commands[name](...args);
