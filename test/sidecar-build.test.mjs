import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { posix } from "node:path";
import { fileURLToPath } from "node:url";

// The frozen emulator finds a module only in a folder build-sidecar.mjs gives PyInstaller with --paths. A folder a case
// module puts on sys.path and the build leaves out is a module missing at run time, and every export check fails.
const root = fileURLToPath(new URL("../", import.meta.url));
const emu = "tools/emu";
const read = rel => readFileSync(`${root}${rel}`, "utf8");

/** The repository folder a sys.path expression of a module in tools/emu names, e.g. ROOT / "tools" / "doom". */
function folderOf(expr) {
  const m = /^(ROOT|Path\(__file__\)(?:\.resolve\(\))?\.(?:parent|parents\[(\d)\]))((?:\s*\/\s*"[^"]+")*)$/.exec(expr.trim());
  if (!m) return null;
  const up = m[1] === "ROOT" ? 2 : m[2] === undefined ? 0 : Number(m[2]);
  const base = m[1] === "ROOT" ? "." : posix.normalize(`${emu}/${"../".repeat(up)}`);
  const parts = [...m[3].matchAll(/"([^"]+)"/g)].map(p => p[1]);
  return posix.normalize(posix.join(base, ...parts)).replace(/\/$/, "");
}

test("build-sidecar gives PyInstaller every folder the bundled modules put on sys.path", () => {
  const build = read(`${emu}/build-sidecar.mjs`);
  const paths = new Set([...build.matchAll(/"--paths", path\("([^"]+)"\)/g)].map(m => posix.normalize(posix.join(emu, m[1])).replace(/\/$/, "")));
  const modules = [...readdirSync(`${root}${emu}`).filter(f => /_cases\.py$/.test(f)), "check.py", "server.py"];
  const missing = [];
  for (const file of modules) {
    const source = read(`${emu}/${file}`);
    const roots = [...source.matchAll(/^ROOT = (.+)$/gm)].map(m => m[1]);
    for (const r of roots) assert.match(r, /Path\(__file__\)\.resolve\(\)\.parents\[2\]/, `${file}: ROOT is the repository`);
    const lines = source.split("\n").filter(l => /^\s*sys\.path(\.insert|\[:0\])/.test(l));
    for (const line of lines) {
      for (const [, expr] of line.matchAll(/str\(((?:[^()]|\([^()]*\))*)\)/g)) {
        const folder = folderOf(expr);
        assert.ok(folder, `${file}: sys.path entry ${expr} not understood, teach this test its folder`);
        const hasModules = existsSync(`${root}${folder}`) && readdirSync(`${root}${folder}`).some(f => f.endsWith(".py"));
        if (hasModules && !paths.has(folder)) missing.push(`${file}: ${folder}`);
      }
    }
  }
  assert.deepEqual(missing, [], "add these folders to --paths in tools/emu/build-sidecar.mjs");
});

test("the folder test reads the forms the case modules use", () => {
  assert.equal(folderOf('ROOT / "tools" / "doom"'), "tools/doom");
  assert.equal(folderOf('ROOT / "tools/patch"'), "tools/patch");
  assert.equal(folderOf("ROOT"), ".");
  assert.equal(folderOf("Path(__file__).parent"), "tools/emu");
  assert.equal(folderOf('Path(__file__).resolve().parents[1] / "patch"'), "tools/patch");
  assert.equal(folderOf("Path(__file__).resolve().parents[2]"), ".");
});
