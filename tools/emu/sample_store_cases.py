"""Run the slot writer against native FatFs in an emulator, using generated samples."""
import argparse
import json
import struct
from pathlib import Path
from unittest.mock import patch

import swap_cases as c
import arm
import sample_store as store

CODE, SCRATCH = 0xC1000000, 0xC3000000
READER, DESCRIPTOR, SOURCE_FIL = CODE + 0x4000, SCRATCH + 0x15000, SCRATCH + 0x16000
LIB_PATH, SOURCE_PATH, GOT = SCRATCH + 0x16400, SCRATCH + 0x16500, SCRATCH + 0x16600


def cases(payload):
    samples = {500: ("old", 100), 501: ("other", 200)}
    entry = c.sampleset.wav(500, "new", 8000)
    original = c.sampleset.build(samples)
    raw = c.plain_wav(2000)
    variants = [("canonical", 503, "pcm16"), ("twentyfour", 504, "pcm24"), ("stereo", 505, "stereo16")]
    extra = {"/input.wav": entry.hex(), "/raw.wav": raw.hex(),
             **{f"/{name}.wav": c.sampleset.wav(500, name, 2000, kind=kind).hex()
                for name, slot, kind in variants}}
    box = c.Box(payload, None, samples, [500], extra=extra)
    folder = c.cardstore.card_folder(payload)
    path = f"KORG/{folder}/Sample/e2sSample.all"
    native_path = ("SD:/" + path).encode()
    symbols = box.sym
    reader = arm.assemble(f"""
    push {{r4-r8, lr}}
    mov r4, r0
    mov r5, r2
    mov r6, r3
    bl {store.API['SEEK']}
    cmp r0, #0
    movne r1, #0
    popne {{r4-r8, pc}}
    mov r0, r4
    mov r1, r5
    mov r2, r6
    ldr r3, ={GOT}
    bl {store.API['READ']}
    ldr r1, ={GOT}
    ldr r1, [r1]
    pop {{r4-r8, pc}}
    .pool
    """, origin=READER).bytes
    box.m.uc.mem_write(READER, reader)
    box.m.uc.mem_write(DESCRIPTOR, struct.pack("<II", READER, SOURCE_FIL))
    box.m.uc.mem_write(LIB_PATH, native_path + b"\0")
    box.m.uc.mem_write(SOURCE_PATH, b"SD:/input.wav\0")
    box.m.uc.ctl_flush_tb()
    opened = box.dev.call(store.API["OPEN"], SOURCE_FIL, SOURCE_PATH, 1)
    result = box.dev.call(symbols["store_put"], LIB_PATH, DESCRIPTOR, 500, len(entry)) if opened == 0 else -1
    closed = box.dev.call(store.API["CLOSE"], SOURCE_FIL) if opened == 0 else -1
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    after = volume.read(path)
    try:
        volume.stat(path[:-3] + "txn")
        no_journal = False
    except c.fat32.NotFound:
        no_journal = True
    volume.close()
    index = struct.unpack_from("<I", after, 16 + 500 * 4)[0]
    out = [dict(id="native_fatfs_put_appends_one_slot", ok=opened == result == closed == 0 and no_journal
                and index == len(original) and after[4096:len(original)] == original[4096:]
                and after[len(original):] == entry and not box.m.asserts,
                status=result, old_bytes=len(original), new_bytes=len(after), journal_removed=no_journal)]
    saved_image = bytes(box.m.mmc.card.medium.data)
    with patch.object(c, "card", lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(saved_image)))):
        rebooted = c.Box(payload, None, samples, [500], record_dsp=True)
    correct = rebooted.resident(500) and rebooted.dsp_bytes(*rebooted.extent(500)) == c.wav_pcm(500, 8000)
    other = rebooted.resident(501) and rebooted.dsp_bytes(*rebooted.extent(501)) == c.wav_pcm(501, 200)
    out.append(dict(id="native_put_survives_reboot", ok=correct and other and not rebooted.m.asserts,
                    new_pcm_equal=correct, other_pcm_equal=other))
    deleted = box.dev.call(symbols["store_delete"], LIB_PATH, 501)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    final = volume.read(path)
    volume.close()
    out.append(dict(id="native_fatfs_delete_keeps_all_other_bytes", ok=deleted == 0 and len(final) == len(after)
                    and final[4096:] == after[4096:] and struct.unpack_from("<I", final, 16 + 501 * 4)[0] == 0
                    and struct.unpack_from("<I", final, 16 + 500 * 4)[0] == index and not box.m.asserts,
                    status=deleted, size_unchanged=len(final) == len(after)))
    box.m.uc.mem_write(SOURCE_PATH, b"SD:/raw.wav\0")
    box.m.uc.mem_write(c.CURSOR, struct.pack("<I", 0x1C65EC0))
    imported = box.dev.call(symbols["store_import"], SOURCE_PATH, 502, LIB_PATH)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    saved = volume.read(path)
    volume.close()
    slot_at = struct.unpack_from("<I", saved, 16 + 502 * 4)[0]
    pcm_length = struct.unpack_from("<I", saved, slot_at + 40)[0] if slot_at else 0
    pcm_equal = bool(slot_at) and saved[slot_at + 44:slot_at + 44 + pcm_length] == raw[44:]
    metadata_at = slot_at + 44 + pcm_length + (pcm_length & 1) + 16
    slot_in_record = struct.unpack_from("<H", saved, metadata_at)[0] if slot_at else None
    out.append(dict(id="plain_wav_import_is_durable_without_free_dsp_space",
                    ok=imported == 0 and pcm_equal and slot_in_record == 502 and box.u32(c.CURSOR) == 0x1C65EC0
                    and saved[4096:len(final)] == final[4096:] and not box.m.asserts,
                    status=imported, target_slot=slot_in_record, pcm_equal=pcm_equal,
                    cursor_unchanged=box.u32(c.CURSOR) == 0x1C65EC0))
    image = bytes(box.m.mmc.card.medium.data)
    with patch.object(c, "card", lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(image)))):
        restored = c.Box(payload, None, samples, [502], record_dsp=True)
    imported_pcm = restored.resident(502) and restored.dsp_bytes(*restored.extent(502)) == raw[44:]
    out.append(dict(id="plain_import_survives_reboot_without_export_all",
                    ok=imported_pcm and not restored.m.asserts, pcm_equal=imported_pcm))
    automatic = box.dev.call(symbols["store_import"], SOURCE_PATH, 0xFFFFFFFF, LIB_PATH)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    chosen = volume.read(path)
    volume.close()
    chosen_at = struct.unpack_from("<I", chosen, 16 + 501 * 4)[0]
    existing = all(struct.unpack_from("<I", chosen, 16 + slot * 4)[0]
                   == struct.unpack_from("<I", saved, 16 + slot * 4)[0] for slot in (500, 502))
    out.append(dict(id="automatic_import_uses_card_index_instead_of_dsp_residency",
                    ok=automatic == 0 and chosen_at == len(saved) and existing
                    and chosen[4096:len(saved)] == saved[4096:] and not box.m.asserts,
                    status=automatic, selected_slot=501 if chosen_at == len(saved) else None,
                    other_indices_unchanged=existing))
    image = bytes(box.m.mmc.card.medium.data)
    with patch.object(c, "card", lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(image)))):
        restored = c.Box(payload, None, samples, [501], record_dsp=True)
    auto_pcm = restored.resident(501) and restored.dsp_bytes(*restored.extent(501)) == raw[44:]
    out.append(dict(id="automatically_selected_slot_survives_reboot_without_export_all",
                    ok=auto_pcm and not restored.m.asserts, pcm_equal=auto_pcm))
    previous = chosen
    for name, slot, kind in variants:
        box.m.uc.mem_write(SOURCE_PATH, f"SD:/{name}.wav".encode() + b"\0")
        imported = box.dev.call(symbols["store_import"], SOURCE_PATH, slot, LIB_PATH)
        volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
        saved = volume.read(path)
        volume.close()
        offset = struct.unpack_from("<I", saved, 16 + slot * 4)[0]
        pcm_size = struct.unpack_from("<I", saved, offset + 40)[0] if offset else 0
        metadata = offset + 44 + pcm_size + (pcm_size & 1) + 16
        indices = tuple(struct.unpack_from("<H", saved, metadata + n)[0] for n in (0, 20, 78)) if offset else ()
        source = bytes.fromhex(extra[f"/{name}.wav"])
        source_size = struct.unpack_from("<I", source, 40)[0]
        equal = bool(offset) and saved[offset + 44:offset + 44 + pcm_size] == source[44:44 + source_size]
        out.append(dict(id=f"{kind}_metadata_is_retargeted_before_persistence",
                        ok=imported == 0 and indices == (slot, slot + 50, slot) and equal
                        and saved[4096:len(previous)] == previous[4096:] and not box.m.asserts,
                        status=imported, metadata_indices=indices, file_pcm_equal=equal))
        previous = saved
    image = bytes(box.m.mmc.card.medium.data)
    with patch.object(c, "card", lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(image)))):
        restored = c.Box(payload, None, samples, [slot for name, slot, kind in variants], record_dsp=True)
    pcm = {kind: restored.resident(slot) and restored.dsp_bytes(*restored.extent(slot)) == c.wav_pcm(500, 2000, kind)
           for name, slot, kind in variants}
    out.append(dict(id="canonical_retargeted_formats_survive_reboot_without_export_all",
                    ok=all(pcm.values()) and not restored.m.asserts, dsp_pcm_equal=pcm))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", required=True, type=Path)
    args = parser.parse_args()
    checks = cases(args.patched.read_bytes()[c.HEADER:])
    print(json.dumps(dict(hardware_contact=False, checks=checks), indent=2))
    return 0 if all(check["ok"] for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
