"""Exercise WAV import through the native Sampler menu on a generated SD card: Korg's import loads the sample into the
DSP and SAMPLE EDIT opens on it as a preview, WRITE keeps it in the card library and EXIT discards it. With a full DSP
the card library takes it at once and the swap loads it on selection."""
import argparse
import json
import struct
from pathlib import Path
from unittest.mock import patch

import swap_cases as c
import lifetime
from dsp_model import DspModel

IMPORT_CALL = 0xC0038DE0
IMPORT_STATUS = 0xC0038DE4
NATIVE_RESERVE = 0xC004EDF0
NATIVE_NAME = 0xC0099788
TARGET = 502
SCREENS, MODEL = 0xC03404C0, 0xC0345A08
SAMPLE_EDIT, BROWSER = 38, 39
NO_PREVIEW = 0xFFFFFFFF
WRITE_KEY = 0x0E
PICK = [("menu", 1), ("turn1", 1), ("menu", 1), ("turn2", 1)]


def ready(box):
    return box.until(lambda: box.u32(c.spec.BOOT_LEASE) == 0 and box.m.screen() == 1, 30.0, 0.2)


def full_dsp(box):
    """Korg's import finds no room in the DSP; returns the cursor values seen when it returns."""
    cursor = box.u32(c.CURSOR)
    seen = []

    def model(uc, at, *_):
        if at == IMPORT_CALL:
            uc.mem_write(c.CURSOR, struct.pack("<I", c.spec.FIRMWARE["DSP_END"]))
        else:
            seen.append(box.u32(c.CURSOR))
            uc.mem_write(c.CURSOR, struct.pack("<I", cursor))

    for at in (IMPORT_CALL, IMPORT_STATUS):
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, model, begin=at, end=at)
    return seen


def screen(box):
    manager = box.u32(SCREENS)
    return box.u32(manager + 0x2C), box.u32(manager + 0x24)


def se_slot(box):
    return box.u32(box.u32(MODEL) + 0x3FC)


def part_samples(box):
    return [box.u16(box.dev.call(c.spec.FIRMWARE["PART"], i) + 0x34) for i in range(16)]


def lit_pads(box):
    return sum(1 for n in range(16) if box.m.leds.get(0x2D + 2 * n, 0))


def play_pad(box, dsp):
    first = len(dsp.gates)
    box.m.send([0x04, 0, 0, 100, 1])
    box.run(0.2)
    box.m.send([0x04, 0, 0, 0, 0])
    box.run(0.4)
    return [p for _, _, p, on in dsp.gates[first:] if on]


def write(box, wait):
    box.m.press(WRITE_KEY, True)
    box.run(0.1)
    box.m.press(WRITE_KEY, False)
    box.run(wait)


def import_to_preview(box):
    """Import the WAV from the menu and wait for SAMPLE EDIT to open on it."""
    found = box.data_utility("import sample")
    for key, wait in PICK:
        if key.startswith("turn"):
            box.dev.turn(int(key[4:]), wait)
        else:
            box.tap(key, wait)
    box.tap("menu", 1.5)
    opened = box.until(lambda: screen(box) == (SAMPLE_EDIT, 0), 5.0)
    box.run(0.5)
    return found, opened


def library(box, path):
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        return volume.read(path)
    except c.fat32.NotFound:
        return b""
    finally:
        volume.close()


def without_target(data, original, missing):
    """The card as before the import; a missing library may meanwhile exist empty, still without the slot."""
    if data == original:
        return True
    return missing and (len(data) < 16 + TARGET * 4 + 4 or struct.unpack_from("<I", data, 16 + TARGET * 4)[0] == 0)


def cases(payload, *, missing=False, large=False, close_failure=False, flash=None):
    samples = {500: ("existing", 1000)}
    if large:
        samples.update(c.sampleset.sized(24, 26 * 1024 * 1024, first=520))
    original = c.sampleset.build({} if missing else samples)
    wave = c.plain_wav(20000)
    pcm = wave[44:]
    path = f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all"
    # with room in the DSP the import is a preview WRITE keeps; a full DSP sends it to the card library at once
    full = large or close_failure

    def remove_library(box):
        volume = c.fat32.Volume(box.m.mmc.card.medium.data)
        try:
            volume.delete(path)
        finally:
            volume.close()

    box = c.Box(payload, flash, samples, [500], extra={"/imp.wav": wave.hex()},
                record_dsp=True, before_boot=remove_library if missing else None)
    started = ready(box)
    dsp = DspModel.attach(box.m)
    targets, statuses, reserves, leases = [], [], [], []
    close_failed = []
    for address, register, rows in (
        (IMPORT_CALL, box.m.A.UC_ARM_REG_R1, targets),
        (IMPORT_STATUS, box.m.A.UC_ARM_REG_R0, statuses),
        (NATIVE_RESERVE, box.m.A.UC_ARM_REG_R0, reserves),
    ):
        def trace(uc, *_args, register=register, rows=rows):
            rows.append(uc.reg_read(register))
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, trace, begin=address, end=address)

    def streaming(*_):
        leases.append(box.u32(c.spec.IMPORT_LOCK))

    for at in (box.sym["import_read"], box.sym["store_put"]):
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, streaming, begin=at, end=at)
    cursor_during_import = full_dsp(box) if full else []
    if close_failure:
        def fail_source_close(uc, *_):
            if leases and not close_failed and uc.reg_read(box.m.A.UC_ARM_REG_R0) == c.spec.FIL:
                close_failed.append(True)
                uc.reg_write(box.m.A.UC_ARM_REG_R0, 1)
                uc.reg_write(box.m.A.UC_ARM_REG_PC, uc.reg_read(box.m.A.UC_ARM_REG_LR))

        close = c.spec.FIRMWARE["F_CLOSE"]
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, fail_source_close, begin=close, end=close)
    before = dict(box.dsp)
    preview = {}
    if full:
        steps = PICK + [("menu", 3), ("menu", 1)]
        found = c.steps_on(box, "import sample", steps)
    else:
        found, opened = import_to_preview(box)
        preview = dict(opened=opened, lit=lit_pads(box), parts=set(part_samples(box)) == {TARGET},
                       resident=box.resident(TARGET), card_unchanged=without_target(library(box, path), original, missing),
                       lock_free=box.u32(c.spec.IMPORT_LOCK) == 0, pad_parts=play_pad(box, dsp))
        write(box, 1.0)
        write(box, 2.0)
        box.until(lambda: box.u32(c.spec.IMPORT_LOCK) == 0 and box.u32(c.spec.FILE_OWNER) == 0, 20.0)
        box.tap("exit", 1.0)
        preview["closed"] = box.until(lambda: screen(box)[0] == BROWSER and box.u32(c.spec.PREVIEW) == NO_PREVIEW, 5.0)
        box.to_main()
    # with the flash busy time modelled, appending to a large library outlasts the menu waits: let the import finish first
    box.until(lambda: box.u32(c.spec.IMPORT_LOCK) == 0, 30.0)
    box.to_main()
    mode_after_import = box.state("MODE")
    data = library(box, path)
    entry_at = struct.unpack_from("<I", data, 16 + TARGET * 4)[0] if len(data) >= 4096 else 0
    expected = bytearray(original)
    if entry_at:
        struct.pack_into("<I", expected, 16 + TARGET * 4, entry_at)
    on_card = (entry_at == len(original) and data[:entry_at] == expected
               and data[entry_at:entry_at + 4] == b"RIFF"
               and data[entry_at + 44:entry_at + 44 + len(pcm)] == pcm)
    still_unloaded = not box.resident(TARGET)
    no_dsp_write = not reserves and before == box.dsp
    loaded_at_import = bool(reserves) and box.resident(TARGET) and box.dsp_bytes(*box.extent(TARGET)) == pcm
    dsp_as_expected = still_unloaded and no_dsp_write if full else loaded_at_import
    previewed = full or (preview["opened"] and preview["lit"] == 16 and preview["parts"] and preview["resident"]
                         and preview["card_unchanged"] and preview["lock_free"] and preview["pad_parts"] == [0]
                         and preview["closed"])
    name = box.dev.call(NATIVE_NAME, TARGET)
    visible = (name == c.NAMES + TARGET * 32 + 12
               and bytes(box.m.uc.mem_read(name, 4)) == b"imp\0")
    loaded_on_demand = False
    if on_card and visible:
        part = box.dev.call(c.spec.FIRMWARE["PART"], 0)
        if missing:
            box.set_parts(box.u32(c.PATPTR) + 4, [TARGET])
            box.m.uc.mem_write(box.u32(part + 8) + 8, struct.pack("<H", TARGET))
            box.dev.call(0xC0099FFC, part)
        else:
            box.m.send([1, 1, 0, 1, 0])
        loaded_on_demand = (
            box.until(lambda: box.resident(TARGET) and box.u16(part + 0x34) == TARGET, 5.0)
            and box.dsp_bytes(*box.extent(TARGET)) == pcm
        )
    rebooted_pcm = None
    if large and on_card:
        image = bytes(box.m.mmc.card.medium.data)
        with patch.object(c, "card", lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(image)))):
            # the boot loads the large sample from the card first: 13.8 s on the red build
            reboot = c.Box(payload, flash, samples, [TARGET], record_dsp=True, boot_limit_s=30.0)
        rebooted_pcm = (ready(reboot) and reboot.resident(TARGET) and reboot.dsp_bytes(*reboot.extent(TARGET)) == pcm
                        and not reboot.m.asserts)
    released = box.u32(c.spec.IMPORT_LOCK) == 0 and box.u32(c.spec.FILE_OWNER) == 0
    locked_while_streaming = bool(leases) and all(value == 1 for value in leases)
    details = dict(mode_after_import=mode_after_import, started=started, found=found, targets=targets, statuses=statuses,
                   preview=preview, card_unchanged=data == original, card_pcm_exact=on_card,
                   initially_unloaded=still_unloaded, no_dsp_write=no_dsp_write, loaded_at_import=loaded_at_import,
                   name_visible=visible, loaded_on_demand=loaded_on_demand, leases=sorted(set(leases)),
                   file_bytes=len(data), modelled_full_cursor=cursor_during_import,
                   rebooted_pcm=rebooted_pcm, lock_released=released, close_failed=bool(close_failed),
                   locked_while_streaming=locked_while_streaming, asserts=box.m.asserts)
    case = ("creates_the_first_library" if missing else "extends_a_large_library" if large
            else "recovers_a_failed_source_close" if close_failure else "appends")
    loads = "only_loads_on_selection" if full else "previews_and_keeps_on_write"
    return [c.entry(f"native_wav_import_{case}_and_{loads}",
                    started and found and targets == [TARGET] and statuses == [4 if close_failure else 0]
                    and mode_after_import == (1 if full else 0) and bool(close_failed) == close_failure and on_card
                    and dsp_as_expected and previewed and visible and loaded_on_demand
                    and locked_while_streaming and released and not box.m.asserts
                    and (not full or cursor_during_import == [c.spec.FIRMWARE["DSP_END"]])
                    and (not large or len(original) > 50 * 1024 * 1024 and rebooted_pcm), details)]


def discard_case(payload, flash=None):
    """EXIT from the preview leaves no trace: not in the DSP, not named, the card and SAMPLE EDIT's slot as before."""
    samples = {500: ("existing", 1000)}
    original = c.sampleset.build(samples)
    path = f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all"
    box = c.Box(payload, flash, samples, [500], extra={"/imp.wav": c.plain_wav(20000).hex()}, record_dsp=True)
    started = ready(box)
    dsp = DspModel.attach(box.m)
    cursor, slot, parts = box.u32(c.CURSOR), se_slot(box), part_samples(box)
    dsp_before = dict(box.dsp)
    found, opened = import_to_preview(box)
    during = dict(opened=opened, lit=lit_pads(box), parts=set(part_samples(box)) == {TARGET},
                  resident=box.resident(TARGET), card_unchanged=library(box, path) == original,
                  pad_parts=play_pad(box, dsp))
    box.tap("exit", 1.0)
    closed = box.until(lambda: screen(box)[0] == BROWSER and box.u32(c.spec.PREVIEW) == NO_PREVIEW, 5.0)
    box.to_main()
    after = dict(closed=closed, resident=box.resident(TARGET),
                 name=bytes(box.m.uc.mem_read(c.NAMES + TARGET * 32 + 12, 16)).rstrip(b"\0").decode("latin-1"),
                 cursor_back=box.u32(c.CURSOR) == cursor, se_slot=se_slot(box) == slot,
                 parts_back=part_samples(box) == parts, dsp_back=box.dsp == dsp_before,
                 card_unchanged=library(box, path) == original,
                 released=box.u32(c.spec.IMPORT_LOCK) == 0 and box.u32(c.spec.FILE_OWNER) == 0)
    ok = (started and found and during["opened"] and during["lit"] == 16 and during["parts"] and during["resident"]
          and during["card_unchanged"] and during["pad_parts"] == [0]
          and after["closed"] and not after["resident"] and after["name"] == "" and after["cursor_back"]
          and after["se_slot"] and after["parts_back"] and after["card_unchanged"] and after["released"]
          and not box.m.asserts)
    return c.entry("native_wav_import_preview_exit_discards", ok,
                   dict(found=found, during=during, after=after, asserts=box.m.asserts))


def occupied_case(payload, flash=None):
    samples = {500: ("offload", 1000), 505: ("active", 1000), 520: ("unused", 10000)}
    before = c.sampleset.build(samples)
    box = c.Box(payload, flash, samples, [505], cap=0x4000,
                extra={"/imp.wav": c.plain_wav(2000).hex()}, record_dsp=True)
    path = f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all"
    pcm_before = dict(box.dsp)
    resident_before = box.resident(500)
    status = []

    def outcome(uc, *_):
        status.append(uc.reg_read(box.m.A.UC_ARM_REG_R0))

    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, outcome, begin=IMPORT_STATUS, end=IMPORT_STATUS)
    found = c.steps_on(box, "import sample", [("menu", 1), ("turn1", 1), ("menu", 1), ("menu", 3)])
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        unchanged = volume.read(path) == before
    finally:
        volume.close()
    no_dsp_write = box.dsp == pcm_before and not box.resident(500)
    return c.entry("native_wav_import_refuses_an_unconfirmed_occupied_card_slot",
                   found and not resident_before and unchanged and no_dsp_write
                   and status == [4] and not box.m.asserts,
                   dict(found=found, initially_resident=resident_before, card_unchanged=unchanged,
                        no_dsp_write=no_dsp_write, status=status, asserts=box.m.asserts))



def admission_case(payload, flash=None):
    samples = {500: ("existing", 1000)}
    before = c.sampleset.build(samples)
    box = c.Box(payload, flash, samples, [500], extra={"/imp.wav": c.plain_wav(2000).hex()})
    transport = box.u32(0xC03405BC)
    transport_state = box.u32(transport + 0x308)
    started = []

    def native_start(*_):
        started.append(True)

    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, native_start, begin=0xC0082F20, end=0xC0082F20)
    box.m.uc.mem_write(c.spec.IMPORT_LOCK, struct.pack("<I", 1))
    rejected_start = box.dev.call(0xC0082F1C, transport, 0)
    lock_after_start = box.u32(c.spec.IMPORT_LOCK)
    box.m.uc.mem_write(c.spec.IMPORT_LOCK, struct.pack("<I", 0))
    statuses = []

    def active_capture(uc, at, *_):
        if at == IMPORT_CALL:
            uc.mem_write(transport + 0x308, struct.pack("<I", 11))
        else:
            statuses.append(uc.reg_read(box.m.A.UC_ARM_REG_R0))
            uc.mem_write(transport + 0x308, struct.pack("<I", transport_state))

    for at in (IMPORT_CALL, IMPORT_STATUS):
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, active_capture, begin=at, end=at)
    steps = [("menu", 1), ("turn1", 1), ("menu", 1), ("turn2", 1), ("menu", 3)]
    found = c.steps_on(box, "import sample", steps)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        unchanged = volume.read(f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all") == before
    finally:
        volume.close()
    released = box.u32(c.spec.IMPORT_LOCK) == 0 and box.u32(c.spec.FILE_OWNER) == 0
    blocked = rejected_start == 0 and not started and lock_after_start == 1
    box.dev.call(0xC0083DB0, 42, 0)
    box.run(0.2)
    normal_start = box.dev.call(0xC0082F1C, transport, 0)
    started_after_import = (normal_start == 1 and started == [True] and box.u32(transport + 0x308) == 11
                            and box.u32(c.spec.IMPORT_LOCK) == 0)
    return c.entry("import_and_native_capture_exclude_each_other",
                   blocked and found and statuses == [4] and unchanged
                   and released and started_after_import and not box.m.asserts,
                   dict(capture_blocked=blocked, found=found, import_statuses=statuses,
                        card_unchanged=unchanged, lock_released=released,
                        normal_capture_still_starts=started_after_import, asserts=box.m.asserts))


def rejected_case(payload, flash, *, missing):
    samples = {500: ("existing", 1000)}
    path = f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all"
    before = None if missing else c.sampleset.build(samples)
    wave = bytearray(c.plain_wav(5000))
    struct.pack_into("<H", wave, 20, 0)

    def remove_library(box):
        volume = c.fat32.Volume(box.m.mmc.card.medium.data)
        try:
            volume.delete(path)
        finally:
            volume.close()

    box = c.Box(payload, flash, samples, [500], extra={"/imp.wav": wave.hex()},
                before_boot=remove_library if missing else None, record_dsp=True)
    started = ready(box)
    calls, statuses = [], []
    for address, register, events in ((IMPORT_CALL, box.m.A.UC_ARM_REG_R1, calls),
                                      (IMPORT_STATUS, box.m.A.UC_ARM_REG_R0, statuses)):
        def trace(uc, *_args, register=register, events=events):
            events.append(uc.reg_read(register))
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, trace, begin=address, end=address)
    pcm = dict(box.dsp)
    found = c.steps_on(box, "import sample",
                       [("menu", 1), ("turn1", 1), ("menu", 1), ("turn2", 1), ("menu", 3)])
    volume = c.fat32.Volume(box.m.mmc.card.medium.data)
    try:
        data = volume.read(path)
    except c.fat32.NotFound:
        data = None
    finally:
        volume.close()
    mode = box.state("MODE")
    uncertain = box.u32(c.spec.FILE_OWNER + 8)
    unchanged = before == data and pcm == box.dsp
    return c.entry("native_wav_import_rejection_preserves_" + ("missing_library" if missing else "stock_mode"),
                   started and found and calls == [TARGET] and statuses == [4] and unchanged
                   and mode == uncertain == 0 and not box.m.asserts,
                   dict(found=found, targets=calls, statuses=statuses, unchanged=unchanged,
                        mode=mode, uncertain=uncertain, asserts=box.m.asserts))


def all_cases(payload, flash=None):
    return (cases(payload, flash=flash) + cases(payload, missing=True, flash=flash)
            + cases(payload, large=True, flash=flash) + cases(payload, close_failure=True, flash=flash)
            + [discard_case(payload, flash), occupied_case(payload, flash), admission_case(payload, flash)])


def main():
    lifetime.load_gate()
    lifetime.exit_with_parent()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", required=True, type=Path)
    parser.add_argument("--only", choices=("append", "missing", "large", "close_failure", "discard", "occupied",
                                           "admission", "rejected"))
    args = parser.parse_args()
    payload = args.patched.read_bytes()[c.HEADER:]
    picks = dict(append=lambda: cases(payload), missing=lambda: cases(payload, missing=True),
                 large=lambda: cases(payload, large=True), close_failure=lambda: cases(payload, close_failure=True),
                 discard=lambda: [discard_case(payload)], occupied=lambda: [occupied_case(payload)],
                 admission=lambda: [admission_case(payload)],
                 rejected=lambda: [rejected_case(payload, None, missing=m) for m in (False, True)])
    checks = picks[args.only]() if args.only else all_cases(payload)
    print(json.dumps(checks, indent=2))
    return 0 if all(case["ok"] for case in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
