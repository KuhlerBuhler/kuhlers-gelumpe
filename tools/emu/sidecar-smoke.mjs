#!/usr/bin/env node
/**
 * Start the frozen emulator (npm run build:sidecar) as the app does and ask it for a quick check.
 *
 *   node tools/emu/sidecar-smoke.mjs [binary]
 *
 * Two all-zero files, no Korg bytes: check.py and its case modules load first, then zeros are no firmware (400).
 * A module the freeze left out is a 500 (server.py).
 */
import { spawn } from "node:child_process";
import { mkdtempSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const VSB_SIZE = 0x200100;
const PORT = 8791;
const TOKEN = "sidecar-smoke";
const dir = fileURLToPath(new URL("../../src-tauri/binaries/", import.meta.url));
const binary = process.argv[2] || join(dir, readdirSync(dir).find(f => f.startsWith("Gelumpe Emulator-")) ?? "");
const temp = mkdtempSync(join(tmpdir(), "gelumpe-sidecar-"));
let log = "";
const service = spawn(binary, ["--port", String(PORT), "--sd-dir", join(temp, "sd"), "--ephemeral", "--parent-pid", String(process.pid)],
  { env: { ...process.env, E2_EMU_TOKEN: TOKEN } });
service.stdout.on("data", d => { log += d; });
service.stderr.on("data", d => { log += d; });
let exited = null;
service.on("exit", code => { exited = code; });
service.on("error", error => { exited = error.message; });

const done = (ok, message) => {
  console.log(log.trim());
  console[ok ? "log" : "error"](message);
  service.kill();
  process.exit(ok ? 0 : 1);
};

let up = false;
for (let i = 0; i < 60 && !up && exited === null; i++) {
  up = await fetch(`http://127.0.0.1:${PORT}/`).then(() => true, () => false);   // any answer, 401 included
  if (!up) await new Promise(r => setTimeout(r, 1000));
}
if (!up) done(false, `The service does not answer (${exited === null ? "no answer after 60 s" : `ended: ${exited}`}).`);

const r = await fetch(`http://127.0.0.1:${PORT}/check?quick=1`, {
  method: "POST", headers: { "X-Emu-Token": TOKEN }, body: new Uint8Array(2 * VSB_SIZE),
});
const text = await r.text();
done(r.status === 400, `POST /check?quick=1 with zeros: ${r.status} ${text}` +
  (r.status === 400 ? "\nThe check and its case modules load." : "\nExpected 400 (no firmware) after the imports."));
