#!/usr/bin/env node
/**
 * Start the local emulator service for the editor page.
 *
 *   npm run emu [-- --port 8740 --page http://127.0.0.1:8737]
 *
 * Uses E2_EMU_PYTHON, else the venv in tools/emu/.venv, else python3. The
 * service prints the link that opens the editor already connected. It stops
 * with this script and with the script that started this one (GELUMPE_PARENT_PID,
 * set by tools/start.mjs), also when either is killed.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const here = new URL("./", import.meta.url);
const venv = fileURLToPath(new URL(process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python", here));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const parents = [process.pid, process.env.GELUMPE_PARENT_PID].filter(Boolean).flatMap(pid => ["--parent-pid", String(pid)]);
const child = spawn(python, [fileURLToPath(new URL("server.py", here)), ...parents, ...process.argv.slice(2)], { stdio: "inherit" });
child.on("error", e => {
  console.error(`Python nicht gefunden (${python}): ${e.message}. Siehe tools/emu/README.md.`);
  process.exit(1);
});
child.on("exit", code => process.exit(code ?? 0));
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(signal, () => child.kill(signal));
process.on("exit", () => child.kill());
