"""Confirmed sample mutations through native menus on generated FAT32 cards."""
import argparse
import json
import struct
from pathlib import Path
from unittest.mock import patch

import swap_cases as c
import sample_import_menu_cases as menu

SAMPLES = {500: ("edited", 1000), 501: ("other", 2000)}


def library(box):
    path = f"KORG/{c.cardstore.card_folder(box.payload)}/Sample/e2sSample.all"
    volume = c.fat32.Volume(box.m.mmc.card.medium.data)
    try:
        return volume.read(path)
    finally:
        volume.close()


def key(box, number, wait=0.4):
    box.m.press(number, True)
    box.run(0.1)
    box.m.press(number, False)
    box.run(wait)


def select_edit(box, slot=500):
    box.to_main()
    box.dev.call(c.SWITCH_SCREEN, 37, 0)
    box.run(0.4)
    manager = box.dev.call(0xC0035AD8)
    if box.dev.call(0xC007DEAC, manager, slot) != 1:
        raise ValueError("native edit target is not loaded")
    current = box.u32(manager + 0x3FC)
    box.dev.call(0xC007EC74, manager, slot - current, 1)
    box.tap("menu", 0.5)
    if not box.m.uc.mem_read(0xC0345A20, 1)[0]:
        raise ValueError("native edit snapshot did not open")
    screen = box.u32(box.u32(box.m.profile.screens) + 0x20)
    imported = box.u16(c.NAMES + slot * 32 + 30) - 50
    return manager, screen, imported


def witnesses(box, *, fail=False):
    statuses, mirrors, injected = [], [], []
    fault = {"active": fail}

    def finished(uc, at, *_):
        register = box.m.A.UC_ARM_REG_R4 if at == 0xC00397FC else box.m.A.UC_ARM_REG_R5
        command = uc.reg_read(register)
        statuses.append(box.m.uc.mem_read(command + 24, 1)[0])

    def mirror(*_):
        mirrors.append(True)

    for at in (0xC00397FC, 0xC00395D8):
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, finished, begin=at, end=at)
    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, mirror, begin=0xC004FB6C, end=0xC004FB6C)
    if fail:
        def refuse(uc, *_):
            if not fault["active"]:
                return
            injected.append(True)
            uc.reg_write(box.m.A.UC_ARM_REG_R0, 1)
            uc.reg_write(box.m.A.UC_ARM_REG_PC, uc.reg_read(box.m.A.UC_ARM_REG_LR))
        at = c.spec.sample_store.API["WRITE"]
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, refuse, begin=at, end=at)
    box.m.uc.ctl_flush_tb()
    return statuses, mirrors, injected, fault


def edit_case(payload, *, write, fail=False, relocated=False, flash=None):
    extra = {"/replacement.wav": c.sampleset.wav(500, "replacement", 1000).hex()} if relocated else None
    box = c.Box(payload, flash, SAMPLES, [500], extra=extra, record_dsp=True)
    ready = menu.ready(box)
    box.m.dsp_mem.update(box.dsp)
    if relocated:
        from sample_snapshot_cases import relocate
        relocate(box, c.wav_pcm(500, 1000))
    before = library(box)
    expected_pcm = box.dsp_bytes(*box.extent(500))
    _, _, imported = select_edit(box)
    old = box.dev.call(0xC004E63C, imported, 0)
    box.dev.call(0xC004E63C, imported, old + 1)
    changed = box.dev.call(0xC004E63C, imported, 0)
    statuses, mirrors, injected, fault = witnesses(box, fail=fail)
    if write:
        key(box, 0x0E, 2.0)
    box.tap("exit", 1.0)
    box.to_main()
    after = box.dev.call(0xC004E63C, imported, 0)
    data = library(box)
    committed = write and not fail
    exact = data == before
    rebooted = True
    diagnostic = {}
    if committed:
        offset = struct.unpack_from("<I", data, 2016)[0]
        count = struct.unpack_from("<I", data, offset + 40)[0]
        expected = bytearray(before)
        struct.pack_into("<I", expected, 2016, len(before))
        start = struct.unpack_from("<I", data, offset + 44 + count + 16 + 40)[0]
        diagnostic.update(offset=offset, expected_offset=len(before), pcm_count=count,
                          expected_pcm=len(expected_pcm), saved_start=start,
                          prefix_exact=data[:len(before)] == expected,
                          pcm_exact=data[offset + 44:offset + 44 + count] == expected_pcm)
        exact = (offset == len(before) and data[:len(before)] == expected
                 and data[offset + 44:offset + 44 + count] == expected_pcm and start == changed * 2)
        image = bytes(box.m.mmc.card.medium.data)
        with patch.object(c, "card", lambda *_a, **_k: c.SDCard(c.MemoryMedium(bytearray(image)))):
            reboot = c.Box(payload, flash, SAMPLES, [500], record_dsp=True)
        boot_ready = menu.ready(reboot)
        selected = reboot.u16(c.NAMES + 500 * 32 + 30) - 50
        rebooted = (boot_ready and reboot.dev.call(0xC004E63C, selected, 0) == changed
                    and reboot.dsp_bytes(*reboot.extent(500)) == expected_pcm and not reboot.m.asserts)
    expected_status = [4 if fail else 0] if write else []
    ok = (ready and changed != old and after == (changed if committed else old)
          and exact and rebooted and statuses == expected_status and not mirrors
          and bool(injected) == fail and not box.m.asserts)
    return c.entry("native_sample_" + ("write_failure" if fail else "write_relocated" if relocated else "write" if write else "edit_exit"), ok,
                   dict(status=statuses, start=[old, changed, after], card_exact=exact, rebooted=rebooted,
                        diagnostic=diagnostic,
                        mirror_calls=len(mirrors), injected=len(injected), asserts=box.m.asserts))


def delete_case(payload, *, fail=False, shared=False, flash=None):
    box = c.Box(payload, flash, SAMPLES, [500], record_dsp=True)
    ready = menu.ready(box)
    box.m.dsp_mem.update(box.dsp)
    before = library(box)
    if shared:
        box.m.uc.mem_write(c.NAMES + 501 * 32 + 30, struct.pack("<H", box.u16(c.NAMES + 500 * 32 + 30)))
        imported = box.u16(c.NAMES + 500 * 32 + 30) - 50
        box.dev.call(0xC004E63C, imported, 1)
    _, screen, _ = select_edit(box)
    box.dev.call(0xC0069538, screen, 9)
    statuses, mirrors, injected, fault = witnesses(box, fail=fail)
    box.tap("menu", 0.4)
    confirmation_only = library(box) == before and box.resident(500) and not statuses
    box.tap("menu", 2.0)
    box.to_main()
    data = library(box)
    expected = bytearray(before)
    if not fail and not shared:
        struct.pack_into("<I", expected, 2016, 0)
    exact = data == expected
    alias_safe = (not shared or box.meta_index(500) == box.meta_index(501)
                  and box.dev.call(box.sym["protection_dirty"], box.meta_index(501)) == 1)
    ok = (ready and confirmation_only and exact and box.resident(500) == (fail or shared)
          and box.resident(501) and alias_safe and statuses == [4 if fail or shared else 0] and not mirrors
          and bool(injected) == fail and not box.m.asserts)
    return c.entry("native_sample_shared_delete_refused" if shared else "native_sample_delete_failure" if fail else "native_sample_delete", ok,
                   dict(status=statuses, confirmed=confirmation_only, card_exact=exact, alias_safe=alias_safe,
                        target_loaded=box.resident(500), other_loaded=box.resident(501),
                        mirror_calls=len(mirrors), injected=len(injected), asserts=box.m.asserts))


def capture_case(payload, *, source=0, stereo=0, write=True, fail=False, offloaded=False, missing=False, library_alias=False, indirect_alias=False, small_alias=False, flash=None):
    def remove_library(box):
        path = f"KORG/{c.cardstore.card_folder(box.payload)}/Sample/e2sSample.all"
        volume = c.fat32.Volume(box.m.mmc.card.medium.data)
        try:
            volume.delete(path)
        finally:
            volume.close()
    library_alias = library_alias or indirect_alias or small_alias
    samples = {501: ("unloaded alias", 1000), 502: ("running", 1000)} if library_alias else SAMPLES
    live = [502] if library_alias else [500]
    target = 503 if library_alias else 500 if missing else 502
    box = c.Box(payload, flash, samples, live, cap=4096 if offloaded or library_alias and not small_alias else None,
                before_boot=remove_library if missing else None, record_dsp=True)
    ready = menu.ready(box)
    box.m.dsp_mem.update(box.dsp)
    if library_alias:
        box.m.uc.mem_write(c.NAMES + 501 * 32 + 30, struct.pack("<H", 650 if indirect_alias else 550))
        if indirect_alias:
            box.m.uc.mem_write(c.spec.FIRMWARE["MAP_A"] + 600 * 32 + 16, struct.pack("<H", 700))
            box.m.uc.mem_write(c.spec.FIRMWARE["MAP_B"] + 700 * 16 + 8, struct.pack("<H", 500))
            box.m.uc.mem_write(c.spec.FIRMWARE["MAP_C"] + 500 * 8 + 2, struct.pack("<H", 504))
        if small_alias:
            box.m.uc.mem_write(c.spec.FIRMWARE["MAP_C"] + 500 * 8 + 2, struct.pack("<H", 501))
        expected_physical = 501 if small_alias else 504 if indirect_alias else 500
        if box.state("MODE") != (0 if small_alias else 1) or box.meta_index(501) != expected_physical or box.resident(501) != small_alias:
            raise ValueError("indexed alias fixture differs")
        prior_alias_extent = box.extent(501) if small_alias else None
    before = c.sampleset.build({}) if missing else library(box)
    transport = box.dev.call(0xC0030D28)
    box.dev.call(0xC0083DB0, 42, 0)
    box.run(0.2)
    manager = box.dev.call(0xC0035AD8)
    outer = box.u32(box.m.profile.screens)
    window = box.u32(outer + 0x24)
    box.dev.call(0xC006B440, window, source)
    box.dev.call(0xC006B3FC, window, stereo)
    selected = (box.u32(manager + 0x708), box.u32(manager + 0x704))
    cursor = box.u32(c.CURSOR)
    started = box.dev.call(0xC0082F1C, transport, int(source == 1))
    box.run(0.2)
    pcm = b"".join(struct.pack("<h", (i * 79 + 137) % 50001 - 25000)
                   for i in range(1024 * (stereo + 1)))
    end = cursor + len(pcm)
    for at in range(0, len(pcm), 2):
        box.m.dsp_mem[cursor + at] = struct.unpack_from("<H", pcm, at)[0]
    box.m.dsp_mem[0xFF903210] = end & 65535
    box.m.dsp_mem[0xFF903212] = end >> 16
    box.dev.call(0xC0082D40, transport)
    box.run(0.2)
    captured = box.u32(transport + 0x308) == 12 and box.resident(target)
    statuses, mirrors, injected, fault = witnesses(box, fail=fail)
    if write:
        key(box, 0x0E, 2.0)
    else:
        box.tap("exit", 1.0)
    failure_state = {}
    if fail:
        physical = box.meta_index(target)
        retained = (library(box) == before and box.resident(target)
                    and box.extent(target) == (cursor, len(pcm))
                    and box.dev.call(box.sym["protection_dirty"], physical) == 1)
        failure_state.update(card_unchanged=library(box) == before, unpersisted_pcm_retained=retained,
                             first_status=list(statuses))
        box.tap("exit", 1.0)
        fault["active"] = False
        select_edit(box, target)
        key(box, 0x0E, 2.0)
    try:
        data = library(box)
    except c.fat32.NotFound:
        return c.entry("native_capture_missing_library", False,
                       dict(ready=ready, selected=selected, started=started, captured=captured,
                            status=statuses, mode=box.state("MODE"),
                            target_loaded=box.resident(target), transport=box.u32(transport + 0x308),
                            owner_uncertain=box.u32(c.spec.FILE_OWNER + 8), asserts=box.m.asserts))
    committed = write
    exact = data == before
    rebooted = True
    if committed:
        offset = struct.unpack_from("<I", data, 16 + target * 4)[0]
        expected = bytearray(before)
        struct.pack_into("<I", expected, 16 + target * 4, len(before))
        channels = struct.unpack_from("<H", data, offset + 22)[0]
        count = struct.unpack_from("<I", data, offset + 40)[0]
        exact = (offset == len(before) and data[:len(before)] == expected
                 and channels == stereo + 1 and count == len(pcm)
                 and data[offset + 44:offset + 44 + count] == pcm)
        image = bytes(box.m.mmc.card.medium.data)
        with patch.object(c, "card", lambda *_a, **_kw: c.SDCard(c.MemoryMedium(bytearray(image)))):
            reboot = c.Box(payload, flash, samples, [live[0], target], cap=4096 if library_alias and not small_alias else None, record_dsp=True)
        rebooted = (menu.ready(reboot) and reboot.resident(target)
                    and reboot.dsp_bytes(*reboot.extent(target)) == pcm and not reboot.m.asserts)
    if not committed:
        exact = exact and not box.resident(target) and box.u32(c.CURSOR) == cursor
    expected_status = [4, 0] if fail else [0]
    alias_safe = (not library_alias or box.resident(501) == small_alias
                  and box.meta_index(501) == (501 if small_alias else 504 if indirect_alias else 500)
                  and (not small_alias or box.extent(501) == prior_alias_extent))
    ok = (ready and selected == (source, stereo) and started == 1 and captured and exact and rebooted
          and alias_safe and statuses == expected_status and not mirrors and bool(injected) == fail and not box.m.asserts
          and (not fail or failure_state["unpersisted_pcm_retained"] and failure_state["first_status"] == [4]))
    return c.entry(f"native_capture_{source}_{stereo}_" + ("small_alias_safe" if small_alias else "indirect_alias_safe" if indirect_alias else "indexed_alias_safe" if library_alias else "first_library" if missing else "offloaded_write" if offloaded else "write_retry" if fail else "write" if write else "discard"), ok,
                   dict(selected=selected, captured=captured, status=statuses, card_exact=exact, alias_safe=alias_safe,
                        failure_state=failure_state,
                        rebooted=rebooted, mirror_calls=len(mirrors), injected=len(injected),
                        audio=False, dma=False, asserts=box.m.asserts))


def cases(payload, flash=None):
    return [edit_case(payload, write=False, flash=flash), edit_case(payload, write=True, flash=flash),
            edit_case(payload, write=True, relocated=True, flash=flash),
            edit_case(payload, write=True, fail=True, flash=flash),
            delete_case(payload, flash=flash), delete_case(payload, fail=True, flash=flash),
            delete_case(payload, shared=True, flash=flash),
            *[capture_case(payload, source=source, stereo=stereo, flash=flash) for source in (0, 1) for stereo in (0, 1)],
            capture_case(payload, write=False, flash=flash), capture_case(payload, fail=True, flash=flash),
            capture_case(payload, offloaded=True, flash=flash), capture_case(payload, missing=True, flash=flash), capture_case(payload, library_alias=True, flash=flash), capture_case(payload, indirect_alias=True, flash=flash), capture_case(payload, small_alias=True, flash=flash)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", required=True, type=Path)
    parser.add_argument("--only", choices=("write", "exit", "write_fail", "delete", "delete_fail", "capture", "discard", "capture_fail", "resample_stereo", "relocated", "offloaded", "missing", "alias_delete", "alias_capture", "indirect_alias", "small_alias"))
    args = parser.parse_args()
    payload = args.patched.read_bytes()[256:]
    selected = {
        "write": lambda: edit_case(payload, write=True),
        "exit": lambda: edit_case(payload, write=False),
        "write_fail": lambda: edit_case(payload, write=True, fail=True),
        "delete": lambda: delete_case(payload),
        "delete_fail": lambda: delete_case(payload, fail=True),
        "capture": lambda: capture_case(payload),
        "discard": lambda: capture_case(payload, write=False),
        "capture_fail": lambda: capture_case(payload, fail=True),
        "resample_stereo": lambda: capture_case(payload, source=1, stereo=1),
        "relocated": lambda: edit_case(payload, write=True, relocated=True),
        "offloaded": lambda: capture_case(payload, offloaded=True),
        "missing": lambda: capture_case(payload, missing=True),
        "alias_delete": lambda: delete_case(payload, shared=True),
        "alias_capture": lambda: capture_case(payload, library_alias=True),
        "indirect_alias": lambda: capture_case(payload, indirect_alias=True),
        "small_alias": lambda: capture_case(payload, small_alias=True),
    }
    rows = [selected[args.only]()] if args.only else cases(payload)
    print(json.dumps(rows, indent=2))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
