#!/usr/bin/env node
/**
 * Freeze the emulator service into one binary for the Tauri app.
 *
 *   npm run build:sidecar
 *
 * Needs the venv from `npm run setup:emu` with PyInstaller in it
 * (tools/emu/requirements-build.txt; installed here if missing). The result
 * is src-tauri/binaries/Gelumpe Emulator-<target triple>, the name Tauri expects
 * for an external binary. No firmware goes in: the binary is only the code.
 */
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { pythonEnv, targetTriple } from "./python-env.mjs";
import { clearCfgInFile } from "./pe-flags.mjs";

const path = rel => fileURLToPath(new URL(rel, import.meta.url));
const win = process.platform === "win32";
const sep = win ? ";" : ":";   // PyInstaller --add-data separator
const { python, command } = pythonEnv();
const run = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  if (r.error || r.status !== 0) {
    console.error(`Fehlgeschlagen: ${cmd} ${args.join(" ")}${r.error ? ` (${r.error.message})` : ""}`);
    process.exit(1);
  }
};

if (!existsSync(python)) run("node", [path("setup.mjs")]);
run(...command(python, ["-m", "pip", "install", "-q", "-r", path("requirements-build.txt")]));

const triple = targetTriple()
  || /^host: (.+)$/m.exec(spawnSync("rustc", ["-vV"], { encoding: "utf8" }).stdout || "")?.[1];
if (!triple) {
  console.error("Zieltriple unbekannt: rustc fehlt. TAURI_TARGET_TRIPLE setzen.");
  process.exit(1);
}

const work = path("../../build/sidecar");
rmSync(work, { recursive: true, force: true });
mkdirSync(work, { recursive: true });
// The frozen bundle holds no .py file to hash, so the boot and result caches get the source's hash from this stamp (bootcache.py).
const [cmd, args] = command(python, ["-c", "import bootcache; print(bootcache.source_hash('patch'))"]);
const stamp = spawnSync(cmd, args, { cwd: path("."), encoding: "utf8" });
if (stamp.error || stamp.status !== 0 || !/^[0-9a-f]{64}$/.test(stamp.stdout.trim())) {
  console.error(`Quellhash fehlgeschlagen: ${stamp.stderr || stamp.error?.message || stamp.stdout}`);
  process.exit(1);
}
writeFileSync(`${work}/source-hash.txt`, stamp.stdout.trim());
run(...command(python, [
  "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
  "--name", "gelumpe-emu",
  "--distpath", `${work}/dist`, "--workpath", `${work}/work`, "--specpath", work,
  // Every folder a case module puts on sys.path (test/sidecar-build.test.mjs holds that): doom_loader_cases imports tools/doom.
  "--paths", path("."), "--paths", path("../patch"), "--paths", path("../doom"),
  "--hidden-import", "machine", "--hidden-import", "check",
  // The check workers import their case modules by name at run time (parallel.py), where PyInstaller sees no import.
  ...readdirSync(path(".")).filter(f => /_cases\.py$/.test(f)).flatMap(f => ["--hidden-import", f.slice(0, -3)]),
  "--collect-all", "unicorn",
  // Our own data the cases and builders read at run time (patch files, Blechy's block, the start image): no firmware.
  "--add-data", `${path("../../data/patches")}${sep}data/patches`,
  "--add-data", `${path("../../data/synth-map")}${sep}data/synth-map`,
  "--add-data", `${path("../../data/script/blechy-block.hex")}${sep}data/script`,
  "--add-data", `${path("../../assets/blechy/splash.bin")}${sep}assets/blechy`,
  "--add-data", `${path("../../assets/blechy/loading.blla")}${sep}assets/blechy`,
  "--add-data", `${work}/source-hash.txt${sep}.`,
  // build_bootstrap reads its layout next to itself; frozen, that is the bundle's root.
  "--add-data", `${path("../doom/layout.json")}${sep}.`,
  // Blechy's sprites and the display font: the power-off and card-error pictures are drawn from them when a check builds them.
  "--add-data", `${path("../../assets/blechy/sprites")}${sep}assets/blechy/sprites`,
  "--add-data", `${path("../../data/script/font.mjs")}${sep}data/script`,
  path("server.py"),
]));

const out = path("../../src-tauri/binaries");
mkdirSync(out, { recursive: true });
// The file's name is what Activity Monitor and the Task Manager show (measured: macOS takes it from the file, not from argv).
const target = `${out}/Gelumpe Emulator-${triple}${win ? ".exe" : ""}`;
copyFileSync(`${work}/dist/gelumpe-emu${win ? ".exe" : ""}`, target);
if (win) clearCfgInFile(target);   // otherwise Windows 10 kills the emulator at the first firmware instruction (pe-flags.mjs)
console.log(`Sidecar: ${target}`);
