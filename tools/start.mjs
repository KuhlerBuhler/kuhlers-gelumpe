#!/usr/bin/env node
/**
 * Start the editor page and the emulator service together.
 *
 *   npm start
 *
 * The page runs on 127.0.0.1:8737 (PORT), the emulator on 8740 (EMU_PORT).
 * The page finds the emulator by itself through /emu.json; Ctrl+C stops both.
 * An emulator that ends by itself is started again on the same port, and the page reconnects.
 */
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";
import { startServer } from "./serve.mjs";

const port = Number(process.env.PORT || 8737);
const emuPort = Number(process.env.EMU_PORT || 8740);

const token = randomBytes(16).toString("base64url");
const server = await startServer(port, { emu: { port: emuPort, token } });
console.log(`Editor läuft auf http://127.0.0.1:${port}/ (verbindet sich selbst mit dem Emulator)`);
let stopping = false;
let emu;
let pause = 500;
function startEmu() {
  const started = Date.now();
  emu = spawn(process.execPath, [
    fileURLToPath(new URL("./emu/start.mjs", import.meta.url)),
    "--port", String(emuPort), "--page", `http://127.0.0.1:${port}`,
  ], { stdio: "inherit", env: { ...process.env, E2_EMU_TOKEN: token, GELUMPE_PARENT_PID: String(process.pid) } });
  emu.on("exit", (code, signal) => {
    if (stopping) {
      server.close();
      process.exit(code ?? 0);
    }
    // Ran for a minute: the next failure starts quickly again. Failing at once: wait longer each time, up to 30 s.
    pause = Date.now() - started > 60_000 ? 1000 : Math.min(pause * 2, 30_000);
    console.error(`Der Emulator ist beendet (${signal ?? code}). Neustart in ${pause / 1000} s.`);
    setTimeout(startEmu, pause);
  });
}
startEmu();
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(signal, () => {
  stopping = true;
  emu.kill(signal);
});
process.on("exit", () => emu.kill());
