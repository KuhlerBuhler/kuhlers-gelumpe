"""Native WAV menu and power-cut checkpoints with a generated FAT32 card."""
import argparse
import json
import struct
import zlib
from pathlib import Path
from unittest.mock import patch

import sample_import_menu_cases as menu
import swap_cases as c

STEPS = [("menu", 1), ("turn1", 1), ("menu", 1), ("turn2", 1), ("menu", 3)]
SAMPLES = {500: ("first", 1000), 501: ("second", 40000)}
WAV = c.plain_wav(5000)
OLD = c.sampleset.build(SAMPLES)
INDEX = 16 + 4 * menu.TARGET
FAULTS = ("full", "cuts", "short_journal", "short_index", "unlink")
PUBLICATION = ("header_empty", "header_short", "journal_empty", "journal_short")
COMMITTED = ("verified_journal", "short_index", "unlink")


def card_state(box, path):
    volume = c.fat32.Volume(box.m.mmc.card.medium.data)
    try:
        data = volume.read(path)
        try:
            journal_bytes = volume.stat(path[:-3] + "txn").size
            if journal_bytes == 0:
                raise AssertionError("unexpected zero-length journal")
        except c.fat32.NotFound:
            journal_bytes = 0
        return data, journal_bytes
    finally:
        volume.close()


def examine(data, *, new, before=OLD):
    index = struct.unpack_from("<I", data, INDEX)[0]
    expected = bytearray(before)
    if new:
        struct.pack_into("<I", expected, INDEX, len(before))
    pcm = data[index + 44:index + len(WAV)] if index else b""
    return dict(index=index, previous_bytes_unchanged=data[:len(before)] == expected,
                new_pcm_exact=(index == len(before) and data[index:index + 4] == b"RIFF" and pcm == WAV[44:]))


def valid(state, *, new, append_offset=len(OLD)):
    return (state["previous_bytes_unchanged"] and state["new_pcm_exact"] == new
            and state["index"] == (append_offset if new else 0))


def full_card(box):
    volume = c.fat32.Volume(box.m.mmc.card.medium.data)
    try:
        volume.write("/KORG/filler.bin", bytes(volume.free_bytes() - 4 * volume.csz))
        if volume.free_bytes() != 4 * volume.csz:
            raise AssertionError("unexpected free space on the near-full FAT32 fixture")
    finally:
        volume.close()


def reboot(payload, flash, image, path, key):
    live = [500, 501] + ([menu.TARGET] if key in COMMITTED else [])
    with patch.object(c, "card", lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(zlib.decompress(image))))):
        box = c.Box(payload, flash, SAMPLES, live, record_dsp=True)
    started = menu.ready(box)
    data, txn = card_state(box, path)
    new = key in COMMITTED
    state = examine(data, new=new)
    old_pcm = all(box.resident(s) and box.dsp_bytes(*box.extent(s)) == c.wav_pcm(s, SAMPLES[s][1]) for s in SAMPLES)
    new_pcm = box.resident(menu.TARGET) and box.dsp_bytes(*box.extent(menu.TARGET)) == WAV[44:]
    retry_status = []
    retry_safe = True
    retry_state = None
    if key == "short_journal":
        def outcome(uc, *_):
            retry_status.append(uc.reg_read(box.m.A.UC_ARM_REG_R0))

        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, outcome, begin=menu.IMPORT_STATUS, end=menu.IMPORT_STATUS)
        found = c.steps_on(box, "import sample", STEPS)
        retry_data, retry_journal = card_state(box, path)
        retry_state = examine(retry_data, new=True, before=data)
        name = box.dev.call(menu.NATIVE_NAME, menu.TARGET)
        named = (name == c.NAMES + menu.TARGET * 32 + 12
                 and bytes(box.m.uc.mem_read(name, 4)) == b"imp\0")
        retry_safe = (found and retry_status == [0] and valid(retry_state, new=True, append_offset=len(data))
                      and retry_journal == 0 and not box.resident(menu.TARGET) and named)
        retry_state.update(name_visible=named, journal_bytes=retry_journal, old_file_bytes=len(data),
                           resident=box.resident(menu.TARGET))
    return dict(**state, ok=(started and valid(state, new=new) and old_pcm and new_pcm == new and retry_safe
                             and txn == 0 and not box.m.asserts),
                old_dsp_pcm_exact=old_pcm, new_dsp_pcm_exact=new_pcm, journal_bytes=txn,
                retry_status=retry_status, retry_safe=retry_safe, retry_state=retry_state, boot_ready=started, asserts=box.m.asserts)


def card_case(payload, flash, fault):
    path = f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all"
    box = c.Box(payload, flash, SAMPLES, [500, 501], extra={"/imp.wav": WAV.hex()},
                before_boot=full_card if fault == "full" else None, record_dsp=True)
    started = menu.ready(box)
    statuses, injected, reserve = [], [], []
    images, snapshots = {}, {}
    importing = False
    streaming = False

    def checkpoint(key):
        data, txn = card_state(box, path)
        snapshots[key] = (struct.unpack_from("<I", data, INDEX)[0], txn)
        images[key] = zlib.compress(box.m.mmc.card.medium.data, level=1)

    def trace(uc, at, *_):
        nonlocal importing, streaming
        if at == menu.IMPORT_CALL:
            importing = True
        elif at == menu.IMPORT_STATUS:
            statuses.append(uc.reg_read(box.m.A.UC_ARM_REG_R0))
            importing = False
        elif importing:
            if at == box.sym["import_read"]:
                streaming = True
            elif at == menu.NATIVE_RESERVE:
                reserve.append(True)
            elif streaming and fault == "cuts" and at == box.sym["store_check_library"]:
                if "before_journal" not in snapshots:
                    checkpoint("before_journal")
            elif streaming and fault == "cuts" and at == box.sym["store_write_index"]:
                checkpoint("verified_journal")
            elif streaming and at == box.sym["catalogue_end_import"] and fault not in ("full", "cuts"):
                checkpoint(fault)

    for at in (menu.IMPORT_CALL, menu.IMPORT_STATUS, menu.NATIVE_RESERVE, box.sym["import_read"],
               box.sym["store_check_library"], box.sym["store_write_index"], box.sym["catalogue_end_import"]):
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, trace, begin=at, end=at)

    def shortened(uc, *_):
        length = 4160 if fault == "short_journal" else 4
        if importing and streaming and not injected and uc.reg_read(box.m.A.UC_ARM_REG_R2) == length:
            sent = 512 if fault == "short_journal" else 2
            injected.append((length, sent))
            uc.reg_write(box.m.A.UC_ARM_REG_R2, sent)

    def unlink_failed(uc, *_):
        if not (importing and streaming and not injected):
            return
        address = uc.reg_read(box.m.A.UC_ARM_REG_R0)
        target = bytes(uc.mem_read(address, 128)).split(b"\0", 1)[0]
        if target.endswith(b".txn"):
            injected.append("unlink")
            uc.reg_write(box.m.A.UC_ARM_REG_R0, 1)
            uc.reg_write(box.m.A.UC_ARM_REG_PC, uc.reg_read(box.m.A.UC_ARM_REG_LR))

    if fault in ("short_journal", "short_index"):
        at = c.spec.sample_store.API["WRITE"]
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, shortened, begin=at, end=at)
    if fault == "unlink":
        at = c.spec.sample_store.API["UNLINK"]
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, unlink_failed, begin=at, end=at)

    pcm_before = dict(box.dsp)
    found = c.steps_on(box, "import sample", STEPS)
    no_upload = not reserve and box.dsp == pcm_before and not box.resident(menu.TARGET)
    final, remaining = card_state(box, path)
    new_final = fault in ("cuts", "short_index", "unlink")
    final_state = examine(final, new=new_final)
    if fault == "full":
        checkpoint(fault)
    rebooted = {key: reboot(payload, flash, image, path, key) for key, image in images.items()}
    expected = {
        "full": (0, 0), "before_journal": (0, 0), "verified_journal": (0, 4160),
        "short_journal": (0, 512), "short_index": (len(OLD) & 0xFFFF, 4160), "unlink": (len(OLD), 4160),
    }
    keys = ("before_journal", "verified_journal") if fault == "cuts" else (fault,)
    ok = (started and found and streaming and statuses == [0 if fault == "cuts" else 4] and no_upload
          and (bool(injected) == (fault not in ("full", "cuts")))
          and not box.m.asserts and valid(final_state, new=new_final)
          and remaining == 0
          and snapshots == {key: expected[key] for key in keys}
          and set(rebooted) == set(keys) and all(row["ok"] for row in rebooted.values()))
    return c.entry("wav_import_card_" + fault, ok,
                   dict(menu_found=found, status=statuses, injected=injected, streamed=streaming,
                        no_dsp_upload=no_upload, before_recovery=snapshots, after_menu=final_state,
                        journal_bytes=remaining, after_reboot=rebooted, asserts=box.m.asserts))


def publication_case(payload, flash, fault):
    first = fault.startswith("header")
    sent = 0 if fault.endswith("empty") else 512 if first else 63
    length = 4096 if first else 4160
    path = f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all"
    journal = path[:-3] + "txn"
    marker = path[:-3] + ("txh" if first else "txp")

    def remove_library(box):
        volume = c.fat32.Volume(box.m.mmc.card.medium.data)
        try:
            volume.delete(path)
        finally:
            volume.close()

    def files(box):
        volume = c.fat32.Volume(box.m.mmc.card.medium.data)
        try:
            values = []
            for name in (path, journal, marker):
                try:
                    values.append(volume.read(name))
                except c.fat32.NotFound:
                    values.append(None)
            return tuple(values)
        finally:
            volume.close()

    def run_menu(box):
        status = []

        def done(uc, *_):
            status.append(uc.reg_read(box.m.A.UC_ARM_REG_R0))

        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, done, begin=menu.IMPORT_STATUS, end=menu.IMPORT_STATUS)
        return c.steps_on(box, "import sample", STEPS), status

    extra = {"/imp.wav": WAV.hex()}
    live = [] if first else [500, 501]
    box = c.Box(payload, flash, SAMPLES, live, extra=extra,
                before_boot=remove_library if first else None, record_dsp=True)
    started = menu.ready(box)
    cut = {}
    injected = []

    def shorten(uc, *_):
        if not injected and uc.reg_read(box.m.A.UC_ARM_REG_R2) == length:
            injected.append(sent)
            uc.reg_write(box.m.A.UC_ARM_REG_R2, sent)

    def before_menu_recovery(*_):
        if injected and not cut:
            lib, txn, witness = files(box)
            fragment = lib if first else txn
            cut.update(image=zlib.compress(box.m.mmc.card.medium.data),
                       bytes=None if fragment is None else len(fragment), marker=witness == b"",
                       previous_bytes=first or (lib is not None and lib[:len(OLD)] == OLD))

    write = c.spec.sample_store.API["WRITE"]
    boundary = box.sym["catalogue_end_import"]
    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, shorten, begin=write, end=write)
    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, before_menu_recovery, begin=boundary, end=boundary)
    first_menu = run_menu(box)
    if not cut:
        return c.entry("wav_import_publication_" + fault, False,
                       dict(boot=started, menu=first_menu, injected=injected, asserts=box.m.asserts))

    image = cut.pop("image")
    with patch.object(c, "card", lambda *_a, **_kw: c.SDCard(c.MemoryMedium(bytearray(zlib.decompress(image))))):
        reboot = c.Box(payload, flash, SAMPLES, live, record_dsp=True)
    ready = menu.ready(reboot)
    lib, txn, witness = files(reboot)
    preserved = lib == c.sampleset.build({}) if first else lib is not None and lib[:len(OLD)] == OLD
    clean = txn is None and witness is None
    old_pcm = all(reboot.resident(slot) and reboot.dsp_bytes(*reboot.extent(slot)) == c.wav_pcm(slot, SAMPLES[slot][1])
                  for slot in live)
    retry = run_menu(reboot)
    data, txn, witness = files(reboot)
    before = c.sampleset.build({}) if first else lib
    exact = (data is not None and before is not None
             and valid(examine(data, new=True, before=before), new=True, append_offset=len(before)))
    ok = (started and first_menu == (True, [4]) and cut == {"bytes": sent, "marker": True, "previous_bytes": True}
          and ready and preserved and clean and old_pcm and retry == (True, [0]) and exact
          and txn is None and witness is None and not reboot.resident(menu.TARGET)
          and not box.m.asserts and not reboot.m.asserts)
    return c.entry("wav_import_publication_" + fault, ok,
                   dict(cut=cut, first_menu=first_menu, boot_ready=ready, previous_bytes=preserved,
                        markers_removed=clean, old_pcm=old_pcm, retry=retry, exact=exact,
                        asserts=box.m.asserts + reboot.m.asserts))


def cases(payload, flash=None, faults=FAULTS):
    return [(publication_case if fault in PUBLICATION else card_case)(payload, flash, fault) for fault in faults]


def main():
    import lifetime
    lifetime.load_gate()
    lifetime.exit_with_parent()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", required=True, type=Path)
    parser.add_argument("--only", choices=FAULTS + PUBLICATION)
    args = parser.parse_args()
    payload = args.patched.read_bytes()[c.HEADER:]
    rows = cases(payload, faults=(args.only,) if args.only else FAULTS + PUBLICATION)
    print(json.dumps(rows, indent=2))
    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
