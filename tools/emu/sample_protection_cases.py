"""Native sample setters and verified boot baselines with generated samples."""
import argparse
import json
import struct
from pathlib import Path

import swap_cases as c
import arm
import unicorn

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


def metadata_store_cases(payload):
    out = []
    for entry, offset, width, value in ((0xC007F980, 20, 2, -1), (0xC007F8A8, 10, 1, 9)):
        box = c.Box(payload, None, c.small(range(500, 506)), [500], cap=0x40000)
        unbind(box)
        original = library(box, payload)
        physical = box.meta_index(500)
        row = c.META + physical * 0x45C
        previous = bytes(box.m.uc.mem_read(row + offset, width))
        box.m.uc.mem_write(c.NAMES + 501 * 32 + 30,
                           bytes(box.m.uc.mem_read(c.NAMES + 500 * 32 + 30, 2)))
        state_call(box, 'mark_clean', 501, box.u32(c.spec.PROTECTION_REV))
        manager, pointer, obj = 0xC100A000, 0xC100A500, 0xC100A600
        box.m.uc.mem_write(manager + 0x3FC, struct.pack('<I', 500))
        box.m.uc.mem_write(pointer, struct.pack('<I', obj))
        box.m.uc.mem_write(obj + 4, struct.pack('<i', value))
        before = state_call(box, 'can_evict', 500)
        box.m.uc.mem_write(obj + 4, struct.pack('<i', int.from_bytes(previous, 'little', signed=True) >> (8 if width == 2 else 0)))
        box.dev.call(entry, manager, pointer, 0)
        identical_marked = state_call(box, 'protection_dirty', physical)
        box.m.uc.mem_write(obj + 4, struct.pack('<i', value))
        store = 0xC007F9F0 if width == 2 else 0xC007F94C
        changed_selection = box.m.uc.hook_add(unicorn.UC_HOOK_CODE,
            lambda uc, *_: uc.mem_write(manager + 0x3FC, struct.pack('<I', 502)), begin=store, end=store)
        box.dev.call(entry, manager, pointer, 0)
        box.m.uc.hook_del(changed_selection)
        box.m.uc.mem_write(manager + 0x3FC, struct.pack('<I', 500))
        changed = int.from_bytes(box.m.uc.mem_read(row + offset, width), 'little')
        marked = state_call(box, 'protection_dirty', physical)
        protected = state_call(box, 'can_evict', 500)
        alias_protected = state_call(box, 'can_evict', 501)
        box.m.uc.mem_write(obj + 4, struct.pack('<i', int.from_bytes(previous, 'little', signed=True) >> (8 if width == 2 else 0)))
        box.dev.call(entry, manager, pointer, 0)
        restored = bytes(box.m.uc.mem_read(row + offset, width)) == previous
        sticky = state_call(box, 'can_evict', 500)
        out.append(dict(id='native_' + ('tune' if width == 2 else 'level') + '_store_protects_all_aliases',
                        ok=before == 1 and changed == ((value << (8 if width == 2 else 0)) & ((1 << (width * 8)) - 1))
                        and identical_marked == 0 and marked == 1 and protected == alias_protected == sticky == 0 and restored
                        and library(box, payload) == original and not box.m.asserts,
                        before=before, changed=changed, marked_before_scan=marked, identical_marked=identical_marked,
                        selection_change_is_model=True, evictable=protected,
                        alias_evictable=alias_protected, restored=restored, restored_evictable=sticky))

    return out


def encoder_store_cases(payload):
    out = []
    for index, offset, width, name, entry in ((5, 20, 2, 'tune', 0xC007F02C),
                                            (8, 10, 1, 'level', 0xC007EF44)):
        box = c.Box(payload, None, c.small(range(500, 506)), [500], cap=0x40000)
        unbind(box)
        physical = box.meta_index(500)
        at = c.META + physical * 0x45C + offset
        previous = bytes(box.m.uc.mem_read(at, width))
        original = library(box, payload)
        manager = box.dev.call(0xC0035AD8)
        box.dev.call(c.SWITCH_SCREEN, 38, 0)
        box.m.uc.mem_write(manager + 0x3FC, struct.pack('<I', 500))
        box.m.uc.mem_write(manager + 0x3F8, struct.pack('<I', index))
        hits = []
        box.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: hits.append(1), begin=entry, end=entry)
        before = state_call(box, 'protection_dirty', physical)
        box.dev.turn(1)
        changed = bytes(box.m.uc.mem_read(at, width)) != previous
        marked = state_call(box, 'protection_dirty', physical)
        box.dev.call(entry, manager, -1, 0)
        restored = bytes(box.m.uc.mem_read(at, width)) == previous
        sticky = state_call(box, 'protection_dirty', physical)
        out.append(dict(id='native_sample_edit_encoder_' + name + '_protects_its_row',
                        ok=before == 0 and changed and marked == sticky == 1 and restored
                        and len(hits) == 2 and library(box, payload) == original and not box.m.asserts,
                        changed=changed, marked_before_scan=marked, restored=restored,
                        sticky=sticky, native_calls=len(hits), real_encoder_forward=True,
                        inverse_is_native_callback=True, selection_setup_is_model=True))
    return out


def pcm_write_cases(payload):
    box = c.Box(payload, None, c.small(range(500, 506)), [500], cap=0x40000, record_dsp=True)
    unbind(box)
    physical = box.meta_index(500)
    regions = ((c.META + physical * 0x45C, 0x45C),
               (c.PLAYBACK + physical * 16, 16), (c.NAMES + 500 * 32, 32))
    tables = [bytes(box.m.uc.mem_read(at, size)) for at, size in regions]
    original = library(box, payload)
    start, _ = box.extent(500)
    previous = box.dsp_bytes(start, 64)
    source = 0xC100B000
    box.m.uc.mem_write(source, bytes((i * 13 + 71) & 255 for i in range(64)))
    box.dev.call(0xC0014284, start, source, 32)
    changed = box.dsp_bytes(start, 64) != previous
    same = tables == [bytes(box.m.uc.mem_read(at, size)) for at, size in regions]
    marked = state_call(box, 'protection_dirty', physical)
    signature = state_call(box, 'slot_clean', 500)
    evictable = state_call(box, 'can_evict', 500)
    unchanged = library(box, payload) == original
    return [dict(id='native_pcm_only_write_protects_its_physical_row',
                 ok=changed and same and marked == 1 and evictable == 0
                 and unchanged and not box.m.asserts,
                 dsp_changed=changed, arm_tables_identical=same, marked_before_scan=marked,
                 signature_clean=signature, evictable=evictable, library_unchanged=unchanged,
                 asserts=box.m.asserts)]


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

    out.extend(metadata_store_cases(payload))
    out.extend(encoder_store_cases(payload))

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
    parser.add_argument('--pcm-write', action='store_true', help='probe PCM-only native writes separately')
    args = parser.parse_args()
    report = (pcm_write_cases if args.pcm_write else cases)(args.patched.read_bytes()[256:])
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report and all(row['ok'] for row in report) else 1)
