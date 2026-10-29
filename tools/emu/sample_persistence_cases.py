"""Measure indexed replacement by appending a generated sample, without writing to a device."""
import argparse
import binascii
import json
import struct
from pathlib import Path
from unittest.mock import patch

import swap_cases as c


def cases(payload):
    samples = {500: ("first", 100), 501: ("second", 100)}
    original = c.sampleset.build(samples)
    replacement = c.sampleset.wav(500, "replacement", 400)
    changed = bytearray(original + replacement)
    struct.pack_into("<I", changed, 16 + 500 * 4, len(original))

    def card(payload, samples, extra=None):
        image = c.fat32.format_image(64 * 1024 * 1024)
        volume = c.fat32.Volume(image)
        volume.write(f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all", changed)
        volume.close()
        return c.SDCard(c.MemoryMedium(image))

    results = []
    with patch.object(c, "card", card):
        for cap in (None, 1024):
            box = c.Box(payload, None, samples, [500], cap=cap, record_dsp=True)
            current = box.resident(500) and box.dsp_bytes(*box.extent(500)) == c.wav_pcm(500, 400)
            if cap is not None:
                box.set_parts(box.u32(c.PATPTR) + 4, [500, 501])
                box.until(lambda: box.resident(501), 3.0)
            other = box.resident(501) and box.dsp_bytes(*box.extent(501)) == c.wav_pcm(501, 100)
            results.append(dict(id="appended_replacement_swap" if cap else "appended_replacement_native",
                                ok=current and other and not box.m.asserts,
                                replacement_pcm_equal=current, other_slot_pcm_equal=other,
                                library_bytes=len(changed), unreachable_old_entry_retained=True,
                                slot_order_differs_from_file_order=True, asserts=len(box.m.asserts)))
    old_header = bytearray(original[:4096])
    intended = bytearray(old_header)
    struct.pack_into("<I", intended, 16 + 500 * 4, len(original))
    journal = bytearray(4160)
    journal[:8] = b"BLECHTX1"
    struct.pack_into("<10I", journal, 8, 1, 1, 500, len(original), len(changed), len(original), len(replacement),
                     binascii.crc32(replacement), binascii.crc32(old_header), binascii.crc32(intended))
    journal[64:] = old_header
    struct.pack_into("<I", journal, 60, binascii.crc32(journal))
    changed[1536:2048] = b"\xA5" * 512

    def interrupted_card(payload, samples, extra=None):
        card_image = card(payload, samples)
        volume = c.fat32.Volume(card_image.medium.data)
        volume.write(f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.txn", journal)
        volume.close()
        return card_image

    with patch.object(c, "card", interrupted_card):
        box = c.Box(payload, None, samples, [500], cap=1024, record_dsp=True)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    path = f"KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all"
    actual = volume.read(path)
    try:
        volume.stat(path[:-3] + "txn")
        journal_removed = False
    except c.fat32.NotFound:
        journal_removed = True
    volume.close()
    pcm_equal = box.resident(500) and box.dsp_bytes(*box.extent(500)) == c.wav_pcm(500, 400)
    results.append(dict(id="interrupted_slot_recovers_before_boot_load",
                        ok=actual[:4096] == intended and journal_removed and pcm_equal and not box.m.asserts,
                        header_restored=actual[:4096] == intended, journal_removed=journal_removed,
                        replacement_pcm_equal=pcm_equal, asserts=len(box.m.asserts)))
    box = c.Box(payload, None, samples, [500], cap=1024, record_dsp=True)
    before = bytes(box.m.uc.mem_read(c.META, c.spec.SAMPLE_COUNT * 0x45C))
    box.m.uc.mem_write(c.spec.STATE + c.spec.OFF["TSTATE"], struct.pack("<I", 1))
    path_at = 0xC1001000
    box.m.uc.mem_write(path_at, f"SD:/KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all\0".encode())
    status = box.dev.call(0xC00364F0, path_at)
    unchanged = bytes(box.m.uc.mem_read(c.META, len(before))) == before
    results.append(dict(id="faulted_library_reload_preserves_live_metadata",
                        ok=status != 0 and unchanged and box.u32(c.spec.STATE + c.spec.OFF["TSTATE"]) == 1
                        and not box.m.asserts, status=status, metadata_unchanged=unchanged,
                        protocol_fault_preserved=box.u32(c.spec.STATE + c.spec.OFF["TSTATE"]) == 1))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", required=True, type=Path)
    args = parser.parse_args()
    result = cases(args.patched.read_bytes()[c.HEADER:])
    print(json.dumps(dict(hardware_contact=False, checks=result), indent=2))
    return 0 if all(check["ok"] for check in result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
