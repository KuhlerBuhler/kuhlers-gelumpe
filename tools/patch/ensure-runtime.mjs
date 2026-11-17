#!/usr/bin/env node
/**
 * Build the runtime patches, which the repository does not carry (AGENTS.md, "Firmware patches").
 *
 *   node tools/patch/ensure-runtime.mjs [--build hacktribe|stock|synth] [--force]
 *
 * data/patches/script-runtime.json, -stock.json and -synth.json are assembled from tools/patch/script_*.s and the
 * Python builders in tools/patch. Committed, they conflicted in every second pull request, and the workflow Update pull
 * requests had to merge, rebuild and push to repair what a text merge made of them. Whoever needs them builds them:
 * this module builds only what is missing or older than the sources, and npm test, npm start, npm run serve,
 * build:site, build:sidecar, check_sets.mjs and verify-patches.mjs call it first.
 *
 * Python 3 is the only requirement; the emulator's venv is used when it exists and E2_EMU_PYTHON names another
 * interpreter. One build takes about four seconds.
 */
import { closeSync, existsSync, mkdirSync, openSync, readdirSync, renameSync, rmSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { buildRuntimePatch } from "./script_runtime.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
export const RUNTIME_BUILDS = ["hacktribe", "stock", "synth"];
// Everything the assembler and the builders after it read. A change in here makes the files stale.
const SOURCE_DIRS = ["tools/patch", "src/script", "data/script"];
// A build that dies leaves its lock behind; after this long the next one takes it over.
const LOCK_STALE_MS = 10 * 60_000;
const LOCK_WAIT_MS = 2 * 60_000;

/** data/patches/script-runtime.json for hacktribe, -stock.json and -synth.json next to it. */
export function runtimePatchPath(build, root = ROOT) {
  if (!RUNTIME_BUILDS.includes(build)) throw new Error(`unknown runtime build: ${build}`);
  return join(root, `data/patches/script-runtime${build === "hacktribe" ? "" : `-${build}`}.json`);
}

/** The youngest source the patches are built from, in ms. */
function newestSource(root) {
  let newest = 0;
  const walk = dir => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith(".") || entry.name === "__pycache__") continue;
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (/\.(s|py|mjs|json|hex)$/.test(entry.name)) newest = Math.max(newest, statSync(path).mtimeMs);
    }
  };
  for (const dir of SOURCE_DIRS) if (existsSync(join(root, dir))) walk(join(root, dir));
  return newest;
}

/** True when the file is missing or older than a source it is built from. */
export function runtimePatchStale(build, root = ROOT) {
  const path = runtimePatchPath(build, root);
  if (!existsSync(path)) return true;
  return statSync(path).mtimeMs <= newestSource(root);
}

const sleep = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

/** Runs `fn` alone for this output file, so two test files and a running `npm start` do not build into each other. */
function withLock(path, fn) {
  const lock = `${path}.lock`;
  const start = Date.now();
  let fd;
  for (;;) {
    try {
      fd = openSync(lock, "wx");
      break;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      try {
        if (Date.now() - statSync(lock).mtimeMs > LOCK_STALE_MS) {
          unlinkSync(lock);
          continue;
        }
      } catch {}
      if (Date.now() - start > LOCK_WAIT_MS) throw new Error(`${lock}: another build does not finish, remove the file if none runs`);
      sleep(100);
    }
  }
  try {
    return fn();
  } finally {
    closeSync(fd);
    rmSync(lock, { force: true });
  }
}

/**
 * Builds every stale runtime patch. Returns [{ build, path, built }] in the order given.
 * `force` builds all of them, whatever their date; `log` gets one line per file it writes.
 */
export function ensureRuntimePatches({ builds = RUNTIME_BUILDS, force = false, log = () => {}, root = ROOT } = {}) {
  const out = [];
  for (const build of builds) {
    const path = runtimePatchPath(build, root);
    if (!force && !runtimePatchStale(build, root)) {
      out.push({ build, path, built: false });
      continue;
    }
    const built = withLock(path, () => {
      // Another process waited with us and was quicker.
      if (!force && !runtimePatchStale(build, root)) return false;
      let text;
      try {
        text = buildRuntimePatch(build);
      } catch (error) {
        throw new Error(`cannot build ${path}: ${error.message}\nThe runtime patches are built, not committed. They need Python 3 (npm run setup:emu sets up the emulator's venv, E2_EMU_PYTHON names another interpreter).`);
      }
      mkdirSync(dirname(path), { recursive: true });
      // Written beside the file and renamed, so a reader sees the old file or the finished one, never half of either.
      const temp = `${path}.${process.pid}.tmp`;
      writeFileSync(temp, text);
      renameSync(temp, path);
      log(`built ${path}`);
      return true;
    });
    out.push({ build, path, built });
  }
  return out;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  try {
    const builds = args.includes("--build") ? [args[args.indexOf("--build") + 1]] : RUNTIME_BUILDS;
    for (const result of ensureRuntimePatches({ builds, force: args.includes("--force"), log: message => console.log(message) })) {
      if (!result.built) console.log(`up to date: ${result.path}`);
    }
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
