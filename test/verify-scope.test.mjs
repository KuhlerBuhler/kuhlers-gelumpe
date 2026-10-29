import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ALL, CASE_MODULES, TABLE, scope, scopeOf } from "../tools/ci/verify-scope.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const read = f => readFileSync(`${root}${f}`, "utf8");

test("the case modules are the ones check.py runs and takes for --cases", () => {
  const check = read("tools/emu/check.py");
  const listed = check.match(/^CASE_MODULES = \(([^)]*)\)/m)[1].match(/"(\w+)"/g).map(s => s.slice(1, -1));
  assert.deepEqual([...listed].sort(), [...CASE_MODULES].sort());
  const imported = [...check.matchAll(/^from (\w+_cases) import .*\bhas_/gm)].map(m => m[1]);
  assert.deepEqual([...new Set(imported)].sort(), [...CASE_MODULES].sort());
});

test("every module in the table is a case module", () => {
  for (const [pattern, modules] of TABLE) {
    if (modules !== ALL) for (const m of modules) assert.ok(CASE_MODULES.includes(m), `${pattern}: ${m}`);
  }
});

test("a changed case module runs itself and every case module that imports from it", () => {
  const importers = m => CASE_MODULES.filter(o => o !== m && new RegExp(`^(from ${m} import|import ${m}\\b)`, "m").test(read(`tools/emu/${o}.py`)));
  const users = m => {
    const seen = new Set([m]);
    for (let todo = [m]; todo.length;) for (const o of importers(todo.pop())) if (!seen.has(o)) { seen.add(o); todo.push(o); }
    return seen;
  };
  for (const m of CASE_MODULES) {
    const s = scopeOf(`tools/emu/${m}.py`);
    if (s !== ALL) assert.deepEqual([...s].sort(), [...users(m)].sort(), m);
  }
});

test("assembly and patch files map to the cases that test them", () => {
  assert.deepEqual(scope(["tools/patch/script_menu.s"]), ["init_pattern_cases", "last_pattern_cases", "menu_cases", "migrate_cases", "shortcut_cases"]);
  assert.deepEqual(scope(["tools/patch/script_remote.s"]), ["remote_cases"]);
  assert.deepEqual(scope(["tools/patch/fx_card.s"]), ["fx_card_cases"]);
  assert.deepEqual(scope(["data/patches/dice.json", "data/patches/dice-synth.json"]), ["dice_cases"]);
  assert.deepEqual(scope(["tools/emu/remote_cases.py", "tools/emu/dice_cases.py"]), ["dice_cases", "remote_cases"]);
});

test("the shared core and any file not in the table mean all", () => {
  for (const f of ["tools/patch/script_vm.s", "tools/patch/script_hooks.s", "src/patch.mjs", "src/hooks.mjs",
    "tools/emu/machine.py", "tools/emu/bootmap.py", "tools/emu/check.py", "tools/emu/splash_cases.py",
    "data/patches/blech.json", "tools/patch/script_new.s", "tools/emu/lcd.py", "src/patcher.mjs",
    ".github/workflows/verify-patches.yml"]) {
    assert.equal(scopeOf(f), ALL, f);
    assert.equal(scope(["tools/patch/script_remote.s", f]), ALL, f);
  }
});

test("files the workflow does not run for add nothing, tests of the tools add nothing", () => {
  assert.deepEqual(scope(["docs/development.md", "test/dice.test.mjs", "data/patches/verified.json", "site/app/main.mjs"]), []);
  assert.deepEqual(scope(["tools/emu/test_lcd.py", "tools/patch/test_script_vm.py"]), []);
  assert.deepEqual(scope(["docs/development.md", "tools/patch/script_remote.s"]), ["remote_cases"]);
});
