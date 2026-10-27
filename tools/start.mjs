#!/usr/bin/env node
/**
 * Start the editor page and the emulator service together.
 *
 *   npm start
 *
 * The page runs on 127.0.0.1:8737 (PORT), the emulator on 8740 (EMU_PORT).
 * The page finds the emulator by itself through /emu.json; Ctrl+C stops both.
 * An emulator that ends by itself is started again on the same port, and the page reconnects.
 *
 * A stop signal ends both for good: no emulator is started after it, and one that does not leave by
 * itself is killed (EMULATOR_END_MS), so a process that stops this way - `docker compose down` stops
 * the container that runs this script - leaves no emulator behind.
 */
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";
import { startServer } from "./serve.mjs";

const port = Number(process.env.PORT || 8737);
const emuPort = Number(process.env.EMU_PORT || 8740);
const host = process.env.GELUMPE_HOST || "127.0.0.1";
// The emulator saves the card and the flash on SIGTERM and gives up on its own after 10 s
// (tools/emu/server.py); past that it is killed, so nothing waits for a service that does not leave.
const EMULATOR_END_MS = 15_000;

const token = randomBytes(16).toString("base64url");
const server = await startServer(port, { host, emu: { port: emuPort, token } });
console.log(`Editor läuft auf http://127.0.0.1:${port}/ (verbindet sich selbst mit dem Emulator)`);
let stopping = false;
let emu = null;                 // the emulator as it runs; null while it is being started again
let restart = null;             // the watchdog's next start, so a stop can call it off
let pause = 500;

/** Ends this process; the emulator is gone by now, or its time to save is up. */
function leave(code) {
  server.close();
  process.exit(code);
}

function startEmu() {
  restart = null;
  const started = Date.now();
  emu = spawn(process.execPath, [
    fileURLToPath(new URL("./emu/start.mjs", import.meta.url)),
    "--port", String(emuPort), "--page", `http://127.0.0.1:${port}`,
  ], { stdio: "inherit", env: { ...process.env, E2_EMU_TOKEN: token, GELUMPE_PARENT_PID: String(process.pid) } });
  emu.on("exit", (code, signal) => {
    emu = null;
    if (stopping) {
      leave(code ?? 0);
      return;
    }
    // Ran for a minute: the next failure starts quickly again. Failing at once: wait longer each time, up to 30 s.
    pause = Date.now() - started > 60_000 ? 1000 : Math.min(pause * 2, 30_000);
    console.error(`Der Emulator ist beendet (${signal ?? code}). Neustart in ${pause / 1000} s.`);
    restart = setTimeout(startEmu, pause);
  });
}

/** The stop signal: the emulator is asked to leave - it saves the card and the flash - and is not started again. */
function stop(signal) {
  if (stopping) {
    emu?.kill("SIGKILL");      // a second Ctrl+C does not wait for the save
    leave(1);
    return;
  }
  stopping = true;
  clearTimeout(restart);
  restart = null;
  if (!emu) {
    leave(0);                  // nothing runs, and nothing is started again
    return;
  }
  emu.kill(signal);
  // Only reached when the emulator is still there after its own 10 s; then it is killed and this ends.
  setTimeout(() => {
    emu?.kill("SIGKILL");
    leave(1);
  }, EMULATOR_END_MS).unref();
}

startEmu();
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(signal, () => stop(signal));
process.on("exit", () => emu?.kill());
