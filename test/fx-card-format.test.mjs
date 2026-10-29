import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { buildCollection, parseCollection, MOD_RECORD } from "../src/fx-collection.mjs";
import { RECORD } from "../src/presets.mjs";

// The emulator cases of tools/emu/fx_card_cases.py build their e2sFx.all in Python, because check.py also runs in the
// app's bundled Python, where there is no node. This keeps that writer byte for byte the editor's: a change to the
// format in src/fx-collection.mjs fails here until the emulator cases (and so tools/patch/fx_card.s) follow it.
const root = fileURLToPath(new URL("../", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const probe = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const available = !probe.error && probe.status === 0;
const required = process.env.E2_ARM_REQUIRED === "1";

const fill = (n, seed) => Uint8Array.from({ length: n }, (_, i) => (i * 7 + seed) & 0xFF);
const ENTRIES = [
  { kind: "ifx", index: 1, data: fill(RECORD, 1), text: '{"format":"gelumpe-fx"}' },
  { kind: "mfx", index: 0, data: fill(RECORD, 2), text: '{"format":"gelumpe-fx","name":"Ä"}' },
  { kind: "mod", index: 3, data: fill(MOD_RECORD, 3), text: "{}" },
];

function pythonCollection(build, entries) {
  const code = `
import json, sys
sys.path.insert(0, "tools/emu")
import fx_card_cases as f
build, entries = json.loads(sys.argv[1])
print(f.collection(build, [f.entry(e["kind"], e["index"], bytes.fromhex(e["data"]), e["text"].encode()) for e in entries]).hex())
`;
  const arg = JSON.stringify([build, entries.map(e => ({ ...e, data: Buffer.from(e.data).toString("hex") }))]);
  const result = spawnSync(python, ["-c", code, arg], { cwd: root, encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  return new Uint8Array(Buffer.from(result.stdout.trim(), "hex"));
}

test("the emulator cases write e2sFx.all byte for byte as the editor does", { skip: !available && !required ? "Unicorn not installed" : false }, () => {
  assert.ok(available, probe.error?.message ?? probe.stderr);
  for (const [build, number] of [["hacktribe", 1], ["stock", 2]]) {
    const editor = buildCollection({ build, entries: ENTRIES });
    assert.deepEqual(pythonCollection(number, ENTRIES), editor, build);
    const back = parseCollection(editor);
    assert.equal(back.ok, true, back.reason);
    assert.equal(back.entries.length, ENTRIES.length);
  }
});
