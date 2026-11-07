#!/usr/bin/env node
/** Build own ARM patch + companion, without reading firmware or contacting a device. */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { asmInclude } from "../../src/script/arm-tables.mjs";
import { compile } from "../../src/script/compiler.mjs";
import { KEY_NAMES } from "../../data/script/names.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));

export async function buildSpettro(build = "hacktribe") {
  if (build !== "hacktribe") throw new Error("Spettro currently supports only Hacktribe Sampler");
  const source = await readFile(new URL("../../data/script/spettro.js", import.meta.url), "utf8");
  const plugin = compile(source, { name: "Spettro" });
  if (!plugin.ok) throw new Error(JSON.stringify(plugin.errors));
  const venv = path.join(root, "tools/emu/.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
  const result = spawnSync(python, ["-B", "-m", "tools.patch.spettro.builder"], {
    cwd: root, encoding: "utf8", maxBuffer: 1 << 26,
    env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
    input: JSON.stringify({ include: asmInclude(), plugin: Buffer.from(plugin.blob).toString("hex"), build }),
  });
  if (result.error || result.status) throw new Error(result.error?.message ?? result.stderr);
  const output = JSON.parse(result.stdout);
  output.layout.keys = Object.fromEntries(KEY_NAMES.map(k => [k.name, k.value]));
  return { ...output, blob: plugin.blob };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const out = process.argv[process.argv.indexOf("--out") + 1];
  if (!process.argv.includes("--out") || !out) throw new Error("Use --out DIRECTORY for the generated patch and companion");
  const result = await buildSpettro();
  await mkdir(out, { recursive: true });
  await writeFile(path.join(out, "Spettro.patch.json"), JSON.stringify(result.patch, null, 2) + "\n");
  await writeFile(path.join(out, "Spettro.layout.json"), JSON.stringify(result.layout, null, 2) + "\n");
  await writeFile(path.join(out, "Spettro.blech"), result.blob);
  console.log(`Built Spettro: ${result.layout.codeBytes} ARM bytes, ${result.blob.length} plugin bytes`);
}
