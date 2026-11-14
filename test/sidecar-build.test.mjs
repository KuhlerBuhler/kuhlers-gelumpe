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

test("build-sidecar bundles the answers the cases once got from Node, where node_json.py looks for them", () => {
  const build = read(`${emu}/build-sidecar.mjs`);
  const helper = read(`${emu}/node_json.py`);
  assert.match(helper, /^DATA = Path\(getattr\(sys, "_MEIPASS", ""\) or REPO\)/m, "frozen, the file is read from the bundle");
  assert.match(helper, /^FILE = DATA \/ "data" \/ "emu" \/ "node-results\.json"$/m);
  assert.match(build, /"--add-data", `\$\{path\("\.\.\/\.\.\/data\/emu\/node-results\.json"\)\}\$\{sep\}data\/emu`/);
});

test("build-sidecar bundles the assembler sources the runtime build reads next to its modules", () => {
  const build = read(`${emu}/build-sidecar.mjs`);
  assert.match(build, /readdirSync\(path\("\.\.\/patch"\)\)\.filter\(f => \/\\\.s\$\/\.test\(f\)\)\.flatMap\(f => \["--add-data", `\$\{path\(`\.\.\/patch\/\$\{f\}`\)\}\$\{sep\}tools\/patch`\]\)/);
  for (const [file, read_] of [["script_vm.py", /Path\(__file__\)\.with_suffix\('\.s'\)\.read_text\(\)/], ["script_hooks.py", /Path\(__file__\)\.with_name\(name\)\.read_text\(\)/]]) {
    assert.match(read(`tools/patch/${file}`), read_, `${file} reads its .s next to itself; the bundle puts it in tools/patch`);
  }
});
