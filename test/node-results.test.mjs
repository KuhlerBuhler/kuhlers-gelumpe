import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The app's emulator is frozen and its users have no Node: what the case modules need from the JavaScript of this
// repository comes from data/emu/node-results.json (tools/emu/node_json.py). These tests keep that file current.
const root = fileURLToPath(new URL("../", import.meta.url));
const emu = `${root}tools/emu`;
const venv = `${emu}/${process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python"}`;
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const modules = readdirSync(emu).filter(f => f.endsWith(".py")).map(f => [f, readFileSync(`${emu}/${f}`, "utf8")]);

test("data/emu/node-results.json holds what the case modules get from Node in this checkout", () => {
  const run = spawnSync(python, [`${emu}/node_results.py`, "--check"], { cwd: root, encoding: "utf8", timeout: 240000 });
  assert.equal(run.error, undefined, `${python}: ${run.error?.message}`);
  assert.equal(run.status, 0, run.stderr || run.stdout);
});

test("no case module starts Node itself", () => {
  // tap_motion_probe.py is a probe for the developer, not part of a check; node_json.py is the one door to Node
  const direct = modules.filter(([f, s]) => f !== "node_json.py" && f !== "tap_motion_probe.py" && /\[\s*["']node["']/.test(s)).map(([f]) => f);
  assert.deepEqual(direct, [], "ask through node_json.py, so the answer goes into data/emu/node-results.json");
});

test("every module that asks Node lists its calls in node_requests()", () => {
  const asks = /\bnode_json\.(run|program|compiled)\(|\bedit\.compiled\(/;
  const missing = modules.filter(([f, s]) => f !== "node_json.py" && f !== "node_results.py" && asks.test(s) && !/^def node_requests\(/m.test(s))
    .map(([f]) => f);
  assert.deepEqual(missing, [], "tools/emu/node_results.py writes only what node_requests() asks for");
});
