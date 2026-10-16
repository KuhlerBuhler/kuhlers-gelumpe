#!/usr/bin/env node
/**
 * Build the script runtime patch for one firmware (VM, input and frame hooks, card loader,
 * display, store, hardware glue) as a public patch. It carries our own code and the checksums of the
 * bytes it replaces; no firmware bytes and no VSB are read.
 *
 *   node tools/patch/script_runtime.mjs [--build hacktribe|stock|synth] [--out patch.json]
 */
import { spawnSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { asmInclude } from "../../src/script/arm-tables.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));

export function buildRuntimePatch(build = "hacktribe") {
  if (!["hacktribe", "stock", "synth"].includes(build)) throw new Error(`unknown runtime build: ${build}`);
  const venv = `${root}tools/emu/.venv/bin/python`;
  const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
  const code = "import json,sys; from tools.patch.script_hooks import build; print(json.dumps(build(sys.stdin.read(), build=sys.argv[1]).patch_manifest(), indent=1, ensure_ascii=False))";
  const result = spawnSync(python, ["-c", code, build], { cwd: root, input: asmInclude(), encoding: "utf8", maxBuffer: 1 << 26 });
  if (result.error || result.status) throw new Error(result.error?.message ?? result.stderr);
  return `${result.stdout.trim()}\n`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const build = process.argv.includes("--build") ? process.argv[process.argv.indexOf("--build") + 1] : "hacktribe";
  const out = process.argv.includes("--out") ? process.argv[process.argv.indexOf("--out") + 1] : `${root}data/patches/script-runtime${build === "hacktribe" ? "" : `-${build}`}.json`;
  writeFileSync(out, buildRuntimePatch(build));
  console.log(`wrote ${out}`);
}
