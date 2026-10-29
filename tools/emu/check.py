# SPDX-License-Identifier: GPL-2.0-only
"""Checks a patched firmware has to pass in the emulator before it is handed out
(docs/patcher.md, "Prüfungen vor dem Export").

Only the patched copy is booted. A changed byte that affects the start is
itself executed or read on the way, so it shows up in the start phase of the
patched copy; one that is never reached cannot change the start.

    tools/emu/.venv/bin/python tools/emu/check.py --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin | --hardware blue] [--boot-flash dump.bin] [--allow 0xF9954:1024] [--allow-code 0x2AEAC:4]

--hardware blue runs every boot on a blank flash of the blue Electribe 2 (its user-data mark), for Sampler code
that runs there (Hacktribe for the blue, docs/ideen/65-blech-hacktribe-blau.md). --boot-flash is a user's own flash for the
start scenarios only; the cases of the patches still run on the --flash/--hardware one, since they expect the Init patterns
of a blank flash (one bar, no chain), not what a user saved (the app's check does this, server.py).

--allow is data of the map's formats that is read at start. --allow-code is an
explicit exception to rule 2 of docs/patcher.md: start-phase code a patch
replaces on purpose, with its reason in the patch (`startPhase`). Every
exception is listed in the result. While it runs, check.py writes one JSON line {"progress": ...} per finished task to stderr (progress.py); stdout is only the result. A copy that carries the splash editor's start
hook also has to pass its storage and kill switch cases (splash_cases.py); one with the MFX 2
switch's key hook has to pass its switch, DSP and kill switch cases (mfx_cases.py); one with the BLECH menu has to pass the menu, settings and look
cases (menu_cases.py); one with the pattern switch has to pass its browse, confirm, EXIT, STOP, chain and stock cases (pswitch_cases.py); one with the TAP motion patch has to pass its toggle, memory, LED, stock, SHIFT, REC, pattern, Master FX and app cases (tap_motion_cases.py); one with the note assistant has to pass its hint, timing, new note, firmware, mode, stock, value and lock cases (note_assist_cases.py); one with the dice has to pass its roll, scale, length, play, LED, key, screen and stock cases (dice_cases.py); one with the idle insert effect has to pass its switch, screen and kill switch cases (ifx_idle_cases.py); a copy with the BLECH menu has to pass the save, reset and kill switch cases of the EXIT shortcuts (shortcut_cases.py) and the copy, skip, choice and no-question cases of the folder copy at the first start (migrate_cases.py), a sampler copy also the cases of the keys from the computer (remote_cases.py); one with the loading bar has to pass its overlay, rescue path and stock cases (loadbar_cases.py); one with the sample error patch has to pass its skip, reason, clean, kill switch and factory slot cases (sample_error_cases.py); one with the synth filters has to pass its key, name, LED, pattern load, round trip and EXIT-at-power-on cases (synth_filter_cases.py); one with the power-off picture's hook has to pass the picture, kill switch and save cases (power_off_cases.py); one with BLECH's SysEx hooks has to pass the protocol, refusal, kill switch and other-SysEx cases (sysex_cases.py).
"""

import argparse
import json
import sys
from pathlib import Path

import bootcache
import parallel
import progress as progress_lib
import taskcache
from bootmap import IMAGE, KILL_SWITCH, START_MODES, combine, scenario_names
from loadbar_cases import GROUPS as LOADBAR_GROUPS, has_hooks as has_loadbar
from machine import hardware_flash, load_flash
from firmware import HARDWARE_MARKS, is_synth
from menu_cases import LOOK_PARTS, has_menu
from mfx_cases import has_key_hook
from pswitch_cases import GROUPS as PSWITCH_GROUPS, has_hooks as has_pswitch
from power_off_cases import cases_tasks as power_off_tasks, has_hook as has_power_off_hook
from preset_cases import has_patch as has_presets
from sample_error_cases import GROUPS as SAMPLEERR_GROUPS, has_hooks as has_sampleerr
from splash_cases import BOOT_CASES, has_start_hook
from synth_filter_cases import GROUPS as SYNTH_GROUPS, has_hooks as has_synth
from sysex_cases import GROUPS as SYSEX_GROUPS, has_hooks as has_sysex
from tap_motion_cases import GROUPS as TAPMOTION_GROUPS, has_hooks as has_tapmotion
from note_assist_cases import GROUPS as NOTEASSIST_GROUPS, has_hooks as has_noteassist
from dice_cases import GROUPS as DICE_GROUPS, has_hooks as has_dice
from ifx_idle_cases import GROUPS as IFXIDLE_GROUPS, has_hooks as has_ifxidle
from shortcut_cases import GROUPS as SHORTCUT_GROUPS, has_hooks as has_shortcuts
from migrate_cases import GROUPS as MIGRATE_GROUPS, has_hooks as has_migrate
from fx_card_cases import GROUPS as FXCARD_GROUPS, has_hooks as has_fxcard
from remote_cases import GROUPS as REMOTE_GROUPS, has_hooks as has_remote
from last_pattern_cases import GROUPS as LASTPATTERN_GROUPS, has_hooks as has_lastpattern
from init_pattern_cases import GROUPS as INITPATTERN_GROUPS, has_hooks as has_initpattern

HEADER = 0x100
PAYLOAD = 0x200000
DSP_STREAM = slice(0xF9F10, 0x13C1B0)    # file offsets, RAM 0xC00F9E10..0xC013C0B0 (2026-10-12-dsp-erster-blick)
SYNTH_DSP_STREAM = slice(0xDFC80, 0x1218F4)


def same_dsp_program(base, patched):
    """The complete DSP upload measured for this firmware build is unchanged."""
    span = SYNTH_DSP_STREAM if is_synth(base[HEADER:]) else DSP_STREAM
    return base[span] == patched[span]


def changed_runs(base, patched):
    """Changed bytes as [file offset, length] runs."""
    runs, i = [], 0
    while i < PAYLOAD:
        if base[i] != patched[i]:
            j = i
            while j < PAYLOAD and base[j] != patched[j]:
                j += 1
            runs.append([HEADER + i, j - i])
            i = j
        else:
            i += 1
    return runs


def overlaps(runs, ranges, allow=()):
    """Parts of the runs (file offsets) inside the ranges (RAM, [start, end)), minus allowed file spans."""
    hits = []
    for file, length in runs:
        lo, hi = IMAGE + file - HEADER, IMAGE + file - HEADER + length
        for s, e in ranges:
            a, b = max(lo, s), min(hi, e)
            if a >= b:
                continue
            # A hit may cross from one allowed span into the next; only what no span covers is left.
            left = [(a - IMAGE + HEADER, b - IMAGE + HEADER)]
            for at, n in allow:
                left = [piece for fa, fb in left
                        for piece in ((fa, min(fb, at)), (max(fa, at + n), fb)) if piece[0] < piece[1]]
            hits.extend([fa, fb - fa] for fa, fb in left)
    return hits


def check(base, patched, flash=None, allow=(), allow_code=(), jobs=None, progress=None, quick=False, boot_flash=None):
    """base and patched are whole VSB files. Returns {ok, checks, changed}. `boot_flash` is the flash the start scenarios
    boot from (default `flash`); the cases of the patches run on `flash`.

    The boots it needs do not depend on each other and run side by side (parallel.py). Each task's result is kept with
    the files it used (taskcache.py), so an unchanged copy is not checked twice and a change runs only the tasks it
    touches; where that cache is off (the app's frozen service) the whole result is kept for the same files and the same
    emulator source (bootcache.py), and then `progress` hears nothing. `progress(snapshot)` is called when the run starts and after every finished task
    (progress.py)."""
    if len(base) != HEADER + PAYLOAD or len(patched) != HEADER + PAYLOAD:
        raise ValueError("a VSB has a 0x100-byte header and a 0x200000-byte payload")
    if taskcache.enabled():
        # each task is kept with the files it used (taskcache.py), data files included, which a key over the .py files
        # of tools/ misses; the rest of the check is quick
        return _check(base, patched, flash, allow, allow_code, jobs, progress, quick, boot_flash)
    return bootcache.cached_result(
        "check-quick" if quick else "check", (bytes(base), bytes(patched), bytes(flash) if flash else b"", sorted(map(tuple, allow)), sorted(map(tuple, allow_code)))
        + ((bytes(boot_flash),) if boot_flash is not None else ()),
        lambda: _check(base, patched, flash, allow, allow_code, jobs, progress, quick, boot_flash))


def _check(base, patched, flash, allow, allow_code, jobs, progress=None, quick=False, boot_flash=None):
    """base and patched are whole VSB files. Returns {ok, checks, changed}. `quick` runs only what keeps the device safe:
    the start scenarios (normal start, update offer, panel update, start modes, EXIT, DSP once, start phase), not the
    cases of the patches, which test the patches' own code, the same in every file."""
    checks = []

    def add(name, ok, detail):
        checks.append({"id": name, "ok": bool(ok), "detail": detail})

    add("header", base[:HEADER] == patched[:HEADER], "der Kopf der VSB ist unverändert")
    # The emulator stubs the DSP upload, so a changed DSP stream never shows up in a boot;
    # a broken block can hang the device before the rescue paths.
    add("dsp_stream", same_dsp_program(base, patched), "der DSP-Strom des Firmware-Builds ist unverändert")
    runs = changed_runs(base[HEADER:], patched[HEADER:])
    payload = patched[HEADER:]
    want = lambda has: not quick and has(payload)
    # longest first: the cases of the patches, then the start scenarios (about a boot each)
    tasks = []
    if want(has_key_hook):
        tasks.append(("mfx_cases", "switch_cases_task", ()))
    if want(has_start_hook):
        tasks += [("splash_cases", "boot_case_task", (i,)) for i in range(BOOT_CASES)]
    if want(has_menu):
        tasks += [("menu_cases", "cases_task", ()), ("menu_cases", "settings_cases_task", ())]
        tasks += [("menu_cases", "look_cases_task", (i,)) for i in range(LOOK_PARTS)]
    if want(has_pswitch):
        tasks += [("pswitch_cases", "cases_task", (i,)) for i in range(len(PSWITCH_GROUPS))]
    if want(has_tapmotion):
        tasks += [("tap_motion_cases", "cases_task", (i,)) for i in range(len(TAPMOTION_GROUPS))]
    if want(has_noteassist):
        tasks += [("note_assist_cases", "cases_task", (i,)) for i in range(len(NOTEASSIST_GROUPS))]
    if want(has_dice):
        tasks += [("dice_cases", "cases_task", (i,)) for i in range(len(DICE_GROUPS))]
    if want(has_ifxidle):
        tasks += [("ifx_idle_cases", "cases_task", (i,)) for i in range(len(IFXIDLE_GROUPS))]
    if want(has_shortcuts):
        tasks += [("shortcut_cases", "cases_task", (i,)) for i in range(len(SHORTCUT_GROUPS))]
    if want(has_migrate):
        tasks += [("migrate_cases", "cases_task", (i,)) for i in range(len(MIGRATE_GROUPS))]
    if want(has_fxcard):
        tasks += [("fx_card_cases", "cases_task", (i,)) for i in range(len(FXCARD_GROUPS))]
    if want(has_remote):
        tasks += [("remote_cases", "cases_task", (i,)) for i in range(len(REMOTE_GROUPS))]
    if want(has_loadbar):
        tasks += [("loadbar_cases", "cases_task", (i,)) for i in range(len(LOADBAR_GROUPS))]
    if want(has_sampleerr):
        tasks += [("sample_error_cases", "cases_task", (i,)) for i in range(len(SAMPLEERR_GROUPS))]
    if want(has_synth):
        tasks += [("synth_filter_cases", "cases_task", (i,)) for i in range(len(SYNTH_GROUPS))]
    if want(has_sysex):
        tasks += [("sysex_cases", "cases_task", (i,)) for i in range(len(SYSEX_GROUPS))]
    if want(has_lastpattern):
        tasks += [("last_pattern_cases", "cases_task", (i,)) for i in range(len(LASTPATTERN_GROUPS))]
    if want(has_initpattern):
        tasks += [("init_pattern_cases", "cases_task", (i,)) for i in range(len(INITPATTERN_GROUPS))]
    power_off, combine_power_off = power_off_tasks(payload) if want(has_power_off_hook) else ([], None)
    tasks += power_off
    if want(has_presets):
        tasks.append(("preset_cases", "cases_task", ()))
    boot = flash if boot_flash is None else boot_flash
    names = scenario_names(boot)
    tasks += [("bootmap", "scenario_task", (name,)) for name in names]
    tracker = progress_lib.Tracker(tasks, parallel.workers(len(tasks)) if jobs is None else jobs, progress) if progress else None
    # Each task's result is kept with the files it used (taskcache.py): a change to one case module runs only its tasks again.
    # Both flashes are shared data and so part of every task's key.
    done = parallel.run_tasks(tasks, {"payload": payload, "flash": flash, "boot_flash": boot, "base": base[HEADER:]}, jobs, tracker.done if tracker else None,
                              cache="check", on_queue=tracker.queued if tracker else None)
    mfx = done.pop(0) if want(has_key_hook) else []
    splash = [done.pop(0) for _ in range(BOOT_CASES)] if want(has_start_hook) else []
    menu = [c for _ in range(2 + LOOK_PARTS if want(has_menu) else 0) for c in done.pop(0)]
    pswitch = [c for _ in range(len(PSWITCH_GROUPS) if want(has_pswitch) else 0) for c in done.pop(0)]
    tapmotion = [c for _ in range(len(TAPMOTION_GROUPS) if want(has_tapmotion) else 0) for c in done.pop(0)]
    noteassist = [c for _ in range(len(NOTEASSIST_GROUPS) if want(has_noteassist) else 0) for c in done.pop(0)]
    dice = [c for _ in range(len(DICE_GROUPS) if want(has_dice) else 0) for c in done.pop(0)]
    ifxidle = [c for _ in range(len(IFXIDLE_GROUPS) if want(has_ifxidle) else 0) for c in done.pop(0)]
    shortcuts = [c for _ in range(len(SHORTCUT_GROUPS) if want(has_shortcuts) else 0) for c in done.pop(0)]
    migrate = [c for _ in range(len(MIGRATE_GROUPS) if want(has_migrate) else 0) for c in done.pop(0)]
    fxcard = [c for _ in range(len(FXCARD_GROUPS) if want(has_fxcard) else 0) for c in done.pop(0)]
    remote = [c for _ in range(len(REMOTE_GROUPS) if want(has_remote) else 0) for c in done.pop(0)]
    loadbar = [c for _ in range(len(LOADBAR_GROUPS) if want(has_loadbar) else 0) for c in done.pop(0)]
    sampleerr = [c for _ in range(len(SAMPLEERR_GROUPS) if want(has_sampleerr) else 0) for c in done.pop(0)]
    synth = [c for _ in range(len(SYNTH_GROUPS) if want(has_synth) else 0) for c in done.pop(0)]
    sysex = [c for _ in range(len(SYSEX_GROUPS) if want(has_sysex) else 0) for c in done.pop(0)]
    lastpattern = [c for _ in range(len(LASTPATTERN_GROUPS) if want(has_lastpattern) else 0) for c in done.pop(0)]
    initpattern = [c for _ in range(len(INITPATTERN_GROUPS) if want(has_initpattern) else 0) for c in done.pop(0)]
    power_off_done = [done.pop(0) for _ in power_off]
    presets = done.pop(0) if want(has_presets) else []
    ranges, report = combine(dict(zip(names, done)))

    def state(name):
        r = report[name]
        return r, (r["panel"] or {}), not r["asserts"]

    for name in ("normal", "normal_blank"):
        if name in report:
            r, _, clean = state(name)
            add(f"boot:{name}", clean and "screen_1" in r["events_ms"],
                "bootet bis zum Hauptbildschirm" + (" mit dem eigenen Flash" if name == "normal" and boot else ""))
    r, p, clean = state("update_offer")
    add("update_offer", clean and p.get("mode") == 10, "ohne Kennung bei Flash 0x220000 kommt die Update-Abfrage")
    r, p, clean = state("panel_update")
    add("panel_update", clean and p.get("panel_update") == 1, "mit falscher Panel-Version kommt das Panel-Update")
    for mask, (mode, label) in START_MODES.items():
        r, p, clean = state(f"held_{mask:08x}")
        ok = clean and p.get("mode") == mode and p.get("held") == mask
        if mask == 0x400:
            ok = ok and p.get("shift_flag") == 1
        add(f"start_mode:{mask:08x}", ok, f"Startmodus {mode} ({label}) erreichbar")
    r, p, clean = state("kill_switch")
    add("kill_switch", clean and p.get("mode") == 0 and p.get("held") == KILL_SWITCH and "screen_1" in r["events_ms"],
        "mit EXIT gehalten normaler Start, Taste im RAM lesbar")
    boots = {name: r["dsp_uploads_ms"] for name, r in report.items()}
    add("dsp_boot_once", all(len(t) == 1 for t in boots.values()),
        "das DSP-Programm wird auf jedem Startweg genau einmal geladen" if all(len(t) == 1 for t in boots.values())
        else {name: t for name, t in boots.items() if len(t) != 1})
    code = overlaps(runs, ranges["code"], allow_code)
    data = overlaps(runs, ranges["data"], [*allow, *allow_code])
    add("start_phase", not code and not data,
        "keine Änderung in Code oder Daten der Startphase" if not code and not data else
        {"code": [[f"0x{a:x}", n] for a, n in code], "data": [[f"0x{a:x}", n] for a, n in data]})
    if allow_code:
        add("start_phase_exceptions", True, "ausdrücklich erlaubt, im Patch begründet: "
            + ", ".join(f"0x{at:x}+{n}" for at, n in allow_code))
    checks.extend(splash)
    checks.extend(mfx)
    checks.extend(menu)
    checks.extend(pswitch)
    checks.extend(tapmotion)
    checks.extend(noteassist)
    checks.extend(dice)
    checks.extend(ifxidle)
    checks.extend(shortcuts)
    checks.extend(migrate)
    checks.extend(fxcard)
    checks.extend(remote)
    checks.extend(loadbar)
    checks.extend(sampleerr)
    checks.extend(synth)
    checks.extend(sysex)
    checks.extend(lastpattern)
    checks.extend(initpattern)
    if power_off:
        checks.extend(combine_power_off(power_off_done))
    checks.extend(presets)
    if quick:
        add("quick", True, "Kurzprüfung: Start und Rettungswege; die Tests der einzelnen Funktionen liefen nicht")
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "changed": [[f"0x{a:x}", n] for a, n in runs]}


def span(text):
    at, n = text.split(":")
    return int(at, 0), int(n, 0)


def main():
    import lifetime
    lifetime.exit_with_parent()      # ends with the test run that started this, also when that is killed
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--allow", action="append", default=[], type=span, metavar="FILE:LEN",
                   help="data the map knows and that may be read at start, e.g. the start image 0xF9954:1024")
    p.add_argument("--hardware", choices=sorted(HARDWARE_MARKS), help="without --flash: a blank flash of this hardware")
    p.add_argument("--boot-flash", nargs="*", default=[], type=Path, help="own flash for the start scenarios only, not the cases")
    p.add_argument("--quick", action="store_true", help="only the start scenarios, not the cases of the patches")
    p.add_argument("--allow-code", action="append", default=[], type=span, metavar="FILE:LEN",
                   help="start-phase code a patch replaces on purpose (docs/patcher.md rule 2), e.g. 0x2AEAC:4")
    a = p.parse_args()
    flash = load_flash(a.flash) if a.flash else bytes(hardware_flash(a.hardware)) if a.hardware else None
    result = check(a.base.read_bytes(), a.patched.read_bytes(), flash, a.allow, a.allow_code,
                   progress=progress_lib.to_stderr, quick=a.quick, boot_flash=load_flash(a.boot_flash) if a.boot_flash else None)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
