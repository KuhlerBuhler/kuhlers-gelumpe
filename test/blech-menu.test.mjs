import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { applyPatches } from "../src/patch.mjs";

// The BLECH menu screen 0x2D (tools/patch/script_menu.s), driven in the firmware emulator.
const SET = JSON.parse(readFileSync(new URL("../data/patches/blech.json", import.meta.url), "utf8"));
const patches = SET.patches.map(path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8")));
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : !local ? "emulation only runs in test:local or test:emu" : false;

test("emulate:2026-10-14/blech-menu, the ring with the page of Blechy at its end, the counter, WRITE, EXIT and the kill switch", { skip }, async () => {
  const applied = await applyPatches(new Uint8Array(readFileSync(vsb)), patches);
  assert.equal(applied.ok, true, applied.reasons.join(" "));
  const folder = mkdtempSync(join(tmpdir(), "blech-menu-"));
  try {
    const path = join(folder, "patched.VSB");
    writeFileSync(path, applied.bytes);
    const run = spawnSync(python(), [join(dir, "emu/menu_cases.py"), "cases", "--base", vsb, "--patched", path, ...(flash.length ? ["--flash", ...flash] : [])],
      { encoding: "utf8", timeout: 900_000, maxBuffer: 4 * 1024 * 1024 });
    assert.ifError(run.error);
    const report = JSON.parse(run.stdout);
    assert.deepEqual(report.filter(c => !c.ok), []);
    for (const id of ["armed", "ring_forward", "ring_backward", "write_opens_nothing", "exit_to_main", "menu_key_returns", "exit_held_is_stock", "pages_are_clean", "tab_labels_fit", "enter_opens_the_list_of_groups", "blechy_follows_event", "blechy_page_shows_him_alone", "blechy_right_goes_to_pattern", "blechy_pattern_left_comes_back", "blechy_left_goes_to_event", "blechy_enter_and_write_do_nothing", "blechy_dial_changes_nothing", "blechy_exit_goes_to_main", "blechy_all_keys_run", "blechy_page_has_no_text", "exit_held_has_no_blechy_page", "look_invert_default_off", "look_invert_on_swaps_the_display", "look_invert_off_swaps_back", "look_invert_start_reads_and_shows_it", "look_invert_exit_held_is_stock", "confirm_default_on", "confirm_dial_acts_at_once", "confirm_file_holds_off", "confirm_start_reads_off", "confirm_exit_held_is_stock"]) {
      assert.ok(report.some(c => c.id === `menu:${id}`), id);
    }
    assert.equal(run.status, 0);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
