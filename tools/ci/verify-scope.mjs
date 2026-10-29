#!/usr/bin/env node
/**
 * Which case modules of tools/emu/check.py a pull request into develop has to run, from the files it changes. The
 * workflow .github/workflows/verify-patches.yml passes the answer to `verify-patches.mjs --cases`; the start scenarios
 * run always.
 *
 *   git diff --name-only origin/develop...HEAD | node tools/ci/verify-scope.mjs      prints "all" or menu_cases,remote_cases
 *
 * A file the workflow's `paths:` filter does not take changes no patched copy and no check, so it adds nothing. Every
 * other file has to be in TABLE; a file that is not, or that the table maps to ALL (the shared core), means every case
 * module. Unknown means all, never less.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));

export const ALL = "all";

/** The case modules check.py runs (CASE_MODULES there; test/verify-scope.test.mjs keeps both the same). */
export const CASE_MODULES = ["mfx_cases", "splash_cases", "menu_cases", "pswitch_cases", "tap_motion_cases",
  "note_assist_cases", "dice_cases", "ifx_idle_cases", "shortcut_cases", "migrate_cases", "fx_card_cases",
  "remote_cases", "loadbar_cases", "sample_error_cases", "synth_filter_cases", "sysex_cases", "last_pattern_cases",
  "init_pattern_cases", "power_off_cases", "preset_cases"];

// The case modules other case modules import helpers from: a change there runs the importers too
// (test/verify-scope.test.mjs reads the imports and fails when one is missing).
const MENU_USERS = ["menu_cases", "shortcut_cases", "migrate_cases", "fx_card_cases", "remote_cases",
  "last_pattern_cases", "init_pattern_cases", "power_off_cases"];
const PSWITCH_USERS = ["pswitch_cases", "tap_motion_cases", "note_assist_cases", "ifx_idle_cases", "shortcut_cases",
  "synth_filter_cases"];
const MFX_USERS = ["mfx_cases", "ifx_idle_cases", "preset_cases"];

/** [pattern, modules or ALL], first match wins. Patterns are anchored; `[^/]*` stays inside one folder. */
export const TABLE = [
  // tests of the tools themselves change no patched copy and no check
  [/^tools\/(emu|patch)\/test_[^/]*\.py$/, []],
  [/^tools\/emu\/(README\.md|LICENSE)$/, []],

  // case modules: the module itself, and the ones that import from it
  [/^tools\/emu\/splash_cases\.py$/, ALL],
  [/^tools\/emu\/menu_cases\.py$/, MENU_USERS],
  [/^tools\/emu\/pswitch_cases\.py$/, PSWITCH_USERS],
  [/^tools\/emu\/mfx_cases\.py$/, MFX_USERS],
  ...CASE_MODULES.map(m => [new RegExp(`^tools/emu/${m}\\.py$`), [m]]),

  // the patches and the code they build, to the cases that test them (check.py's docstring, each has_hooks)
  [/^tools\/patch\/mfx_switch\.py$|^data\/patches\/mfx-switch[^/]*\.json$/, MFX_USERS],
  [/^tools\/patch\/(splash_editor\.py|splash_synth\.mjs)$|^data\/patches\/splash-(editor|synth)[^/]*\.json$/, ["splash_cases"]],
  [/^tools\/patch\/script_menu\.s$/, ["menu_cases", "shortcut_cases", "migrate_cases", "init_pattern_cases"]],
  [/^tools\/patch\/blech_version\.mjs$|^data\/patches\/blech-version[^/]*\.json$/, ["menu_cases"]],
  [/^tools\/patch\/script_shortcuts\.s$/, ["shortcut_cases"]],
  [/^tools\/patch\/script_migrate\.s$/, ["migrate_cases"]],
  [/^tools\/patch\/script_remote\.s$/, ["remote_cases"]],
  [/^tools\/patch\/fx_card\.s$/, ["fx_card_cases"]],
  [/^tools\/patch\/pattern_switch\.py$|^data\/patches\/pattern-switch[^/]*\.json$/, ["pswitch_cases"]],
  [/^tools\/patch\/tap_motion\.py$|^data\/patches\/tap-motion[^/]*\.json$/, ["tap_motion_cases"]],
  [/^tools\/patch\/note_assist\.py$|^data\/patches\/note-assistant[^/]*\.json$/, ["note_assist_cases"]],
  [/^tools\/patch\/dice\.py$|^data\/patches\/dice[^/]*\.json$/, ["dice_cases"]],
  [/^tools\/patch\/ifx_idle\.py$|^data\/patches\/ifx-idle[^/]*\.json$/, ["ifx_idle_cases"]],
  [/^tools\/patch\/(load_bar|loading_anim)\.py$|^data\/patches\/load-bar[^/]*\.json$/, ["loadbar_cases"]],
  [/^tools\/patch\/sample_errors\.py$|^data\/patches\/sample-errors[^/]*\.json$/, ["sample_error_cases"]],
  [/^tools\/patch\/synth_filters\.py$|^data\/patches\/synth-filters[^/]*\.json$/, ["synth_filter_cases"]],
  [/^tools\/patch\/blech_sysex\.(py|mjs)$|^data\/patches\/blech-sysex[^/]*\.json$/, ["sysex_cases"]],
  [/^tools\/patch\/last_pattern\.py$|^data\/patches\/last-pattern[^/]*\.json$/, ["last_pattern_cases"]],
  [/^tools\/patch\/init_pattern\.py$|^data\/patches\/init-pattern[^/]*\.json$/, ["init_pattern_cases"]],
  [/^tools\/patch\/power_off\.py$|^data\/patches\/power-off[^/]*\.json$/, ["power_off_cases"]],
  [/^tools\/patch\/preset_tables\.py$|^data\/patches\/preset-tables[^/]*\.json$/, ["preset_cases"]],

  // the shared core: the script VM and its hooks, the patcher, the emulator and check.py itself. Listed so the
  // intent is written down; anything else not matched above is ALL as well.
  [/^tools\/patch\/script_(vm|hooks)\.(s|py)$/, ALL],
  [/^src\/(patch|hooks)\.mjs$/, ALL],
  [/^tools\/emu\/(machine|bootmap|check)\.py$/, ALL],
];

/** The workflow's `paths:` filter as a test: true for a file whose change starts the workflow. */
export function workflowPaths(text = readFileSync(`${root}.github/workflows/verify-patches.yml`, "utf8")) {
  const block = text.match(/^ {4}paths:\n((?: {6}- .*\n)+)/m)[1];
  const globs = [...block.matchAll(/- "([^"]+)"/g)].map(m => m[1]);
  const re = g => new RegExp(`^${g.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*\*/g, "\0").replace(/\*/g, "[^/]*").replace(/\0/g, ".*")}$`);
  const take = globs.filter(g => !g.startsWith("!")).map(re);
  const drop = globs.filter(g => g.startsWith("!")).map(g => re(g.slice(1)));
  return f => take.some(r => r.test(f)) && !drop.some(r => r.test(f));
}

/** The case modules for one changed file: an array, or ALL. */
export function scopeOf(file) {
  const hit = TABLE.find(([pattern]) => pattern.test(file));
  return hit ? hit[1] : ALL;
}

/** The case modules for the changed files: ALL, or a sorted array (empty: only the start scenarios). */
export function scope(files, relevant = workflowPaths()) {
  const modules = new Set();
  for (const file of files.filter(relevant)) {
    const s = scopeOf(file);
    if (s === ALL) return ALL;
    s.forEach(m => modules.add(m));
  }
  return [...modules].sort();
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const files = (args.length ? args : readFileSync(0, "utf8").split("\n")).map(f => f.trim()).filter(Boolean);
  const s = scope(files);
  console.log(s === ALL ? ALL : s.join(","));
}
