#!/usr/bin/env node
/**
 * Create tools/emu/.venv and install the pinned Unicorn into it.
 *
 *   npm run setup:emu
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { pythonEnv } from "./python-env.mjs";

const here = new URL("./", import.meta.url);
const { dir, python, basePython, command } = pythonEnv();
const run = (cmd, args) => {
  const r = spawnSync(cmd, args, { stdio: "inherit" });
  if (r.error || r.status !== 0) {
    console.error(`Fehlgeschlagen: ${cmd} ${args.join(" ")}${r.error ? ` (${r.error.message})` : ""}`);
    process.exit(1);
  }
};
const base = basePython ? [basePython] : process.platform === "win32" ? ["py", "-3"] : ["python3"];
if (!existsSync(python)) run(...command(base[0], [...base.slice(1), "-m", "venv", dir]));
run(...command(python, ["-m", "pip", "install", "-q", "-r", fileURLToPath(new URL("requirements.txt", here))]));
console.log(`Emulator eingerichtet: ${python}`);
