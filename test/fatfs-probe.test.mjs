import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ARCHIVE } from "../data/script/contract.mjs";

// tools/device/fatfs_probe.py is the file read and write test that is run on the device. It must
// assemble without a venv, fit the 1 KiB execute buffer, use the contract folder, and pass in the
// emulator against the firmware's own FatFs with a virtual card.
const dir = fileURLToPath(new URL("../tools/device/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const probe = spawnSync(python, ["--version"], { encoding: "utf8" });
const skip = probe.error ? `${python} not available` : false;
const firmwareRequired = process.env.E2_EMU_REQUIRED === "1" || process.env.E2_LOCAL_REQUIRED === "1";

test("fatfs_probe: the stub assembles, fits the execute buffer and reads and writes in the contract folder", { skip }, () => {
  const code = "import fatfs_probe as p; s = p.stub(3, bytes(64)); print(len(s), p.FOLDER)";
  const r = spawnSync(python, ["-c", code], { encoding: "utf8", cwd: dir });
  assert.ifError(r.error);
  assert.equal(r.status, 0, r.stderr);
  const [size, folder] = r.stdout.trim().split(" ");
  assert.ok(Number(size) <= 1024, `stub is ${size} bytes`);
  assert.equal(folder, `SD:${ARCHIVE.folder}/`);
});

test("fatfs_probe: in the emulator the read test, the write test and the file on the card agree", {
  skip: skip || (!firmwareRequired && !process.env.E2_VSB ? "firmware emulation requires E2_VSB" : false),
}, () => {
  assert.ok(process.env.E2_VSB, "E2_VSB must name the local firmware");
  const r = spawnSync(python, ["fatfs_probe.py", "--emu", process.env.E2_VSB], { encoding: "utf8", cwd: dir, timeout: 300_000 });
  assert.ifError(r.error);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /all checks passed/);
  assert.match(r.stdout, /FSTEST\.OUT on the card equals what was sent: True/);
});
