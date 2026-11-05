"""Native sample setters and verified boot baselines with generated samples."""
import argparse
import json
import struct
from pathlib import Path

import swap_cases as c
import arm

ADAPTER, SOURCE_PATH, LIB_PATH = 0xC1000000, 0xC1008000, 0xC1008100


def state_call(box, label, *args):
    source = f'''push {{r3, r4, r11, lr}}
    ldr r11, ={c.spec.STATE}
    bl {box.sym[label]}
    pop {{r3, r4, r11, pc}}
    .pool'''
    box.m.uc.mem_write(ADAPTER, arm.assemble(source, origin=ADAPTER).bytes)
    return box.dev.call(ADAPTER, *args)


def unbind(box):
    box.set_parts(box.u32(c.PATPTR) + 4, [])
    box.m.uc.mem_write(c.spec.STATE + c.spec.PROT, b'\xff' * 64)
    for part in range(16):
        at = box.dev.call(c.spec.FIRMWARE['PART'], part)
        box.m.uc.mem_write(at + 0x34, b'\xff\xff')


def library(box, payload):
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        return volume.read(f'KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all')
    finally:
        volume.close()


def cases(payload):
    out = []
    box = c.Box(payload, None, c.small(range(500, 506)), [500], cap=0x40000)
    unbind(box)
    original = library(box, payload)
    baseline = box.u32(c.spec.SIG + 500 * 4)
    before = state_call(box, 'can_evict', 500)
    raw = box.u16(c.NAMES + 500 * 32 + 30) - 50
    box.dev.call(0xC004E63C, raw, 0)
    getter = state_call(box, 'can_evict', 500)
    box.dev.call(0xC004E63C, raw, 1)
    edited = state_call(box, 'can_evict', 500)
    out.append(dict(id='native_start_edit_protects_the_boot_loaded_row',
                    ok=baseline != 0 and before == getter == 1 and edited == 0
                    and library(box, payload) == original and not box.m.asserts,
                    baseline=baseline, before=before, getter=getter, after=edited))

    samples = {500: ('old', 20000), **c.small(range(501, 506))}
    box = c.Box(payload, None, samples, [500], cap=0x40000, record_dsp=True,
                extra={'/replacement.wav': c.plain_wav(20000).hex()})
    unbind(box)
    original = library(box, payload)
    physical = box.meta_index(500)
    names = bytes(box.m.uc.mem_read(c.NAMES + 500 * 32, 32))
    playback = bytes(box.m.uc.mem_read(c.PLAYBACK + physical * 16, 16))
    meta = bytes(box.m.uc.mem_read(c.META + physical * 0x45C, 0x45C))
    old_extent = box.extent(500)
    old_pcm = box.dsp_bytes(*old_extent)
    box.m.uc.mem_write(SOURCE_PATH, b'SD:/replacement.wav\0')
    imported = box.dev.call(0xC003644C, SOURCE_PATH, 500)
    new_extent = box.extent(500)
    changed_pcm = box.dsp_bytes(*new_extent) != old_pcm
    box.m.uc.mem_write(c.NAMES + 500 * 32, names)
    box.m.uc.mem_write(c.PLAYBACK + physical * 16, playback)
    box.m.uc.mem_write(c.META + physical * 0x45C, meta)
    clean_signature = state_call(box, 'slot_clean', 500)
    allowed = state_call(box, 'can_evict', 500)
    out.append(dict(id='native_equal_length_import_stays_protected_after_metadata_restore',
                    ok=imported == 0 and old_extent == new_extent and changed_pcm
                    and clean_signature == 1 and allowed == 0
                    and library(box, payload) == original and not box.m.asserts,
                    imported=imported, old_extent=old_extent, new_extent=new_extent,
                    changed_pcm=changed_pcm, signature_equal=clean_signature, evictable=allowed,
                    metadata_restore_is_model=True))

    samples = {500: ('first', 100), 501: ('other', 200)}
    box = c.Box(payload, None, samples, [500], cap=0x6000,
                extra={'/grow.wav': c.plain_wav(12000).hex()})
    unbind(box)
    before_mode = box.state('MODE')
    baseline = box.u32(c.spec.SIG + 501 * 4)
    box.m.uc.mem_write(SOURCE_PATH, b'SD:/grow.wav\0')
    native_path = f'SD:/KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all'.encode() + b'\0'
    box.m.uc.mem_write(LIB_PATH, native_path)
    acquired = box.dev.call(box.sym['catalogue_begin'])
    token = box.u32(c.spec.FILE_OWNER)
    imported = box.dev.call(box.sym['store_import'], SOURCE_PATH, 502, LIB_PATH) if acquired == 0 else -1
    completed = box.dev.call(box.sym['catalogue_end'], token, imported) if acquired == 0 else -1
    allowed = state_call(box, 'can_evict', 501)
    out.append(dict(id='small_library_retains_verified_baselines_when_it_grows',
                    ok=before_mode == 0 and baseline != 0 and acquired == imported == completed == 0
                    and box.state('MODE') == 1 and allowed == 1 and not box.m.asserts,
                    before_mode=before_mode, after_mode=box.state('MODE'), baseline=baseline,
                    acquired=acquired, imported=imported, completed=completed, evictable=allowed))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', required=True, type=Path)
    args = parser.parse_args()
    report = cases(args.patched.read_bytes()[256:])
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report and all(row['ok'] for row in report) else 1)
