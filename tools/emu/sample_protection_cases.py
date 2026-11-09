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



def pcm_boot_cases(payload):
    out = []
    for dynamic in (False, True):
        for foreign in (False, True):
            seen = {'writes': 0, 'injected': False}

            def setup(box):
                box.m.uc.mem_write(0xC100B000, bytes((i * 17 + 39) & 255 for i in range(64)))

                def inject(uc, *_):
                    from unicorn import arm_const as R
                    destination = uc.reg_read(R.UC_ARM_REG_R1)
                    if not c.DSP_MIN <= destination < c.spec.FIRMWARE['DSP_END']:
                        return
                    seen['writes'] += 1
                    if not foreign or seen['injected'] or destination <= c.DSP_MIN:
                        return
                    seen['injected'] = True
                    origin = 0xC100C000
                    code = f"""push {{r0-r12, lr}}
                    .word 0xE10F4000
                    push {{r4, r5}}
                    ldr r0, =0x60000000
                    ldr r1, ={c.DSP_MIN}
                    ldr r2, =0xC100B000
                    mov r3, #16
                    bl 0xC00146B4
                    pop {{r4, r5}}
                    .word 0xE121F004
                    .word 0xE128F004
                    pop {{r0-r12, lr}}
                    b 0xC00146B4
                    .pool"""
                    uc.mem_write(origin, arm.assemble(code, origin=origin).bytes)
                    uc.reg_write(R.UC_ARM_REG_PC, origin)

                box.m.uc.hook_add(unicorn.UC_HOOK_CODE, inject, begin=0xC00146B4, end=0xC00146B4)

            samples = c.small(range(500, 506)) if dynamic else c.small([500])
            box = c.Box(payload, None, samples, [500], cap=0x40000,
                        record_dsp=True, before_boot=setup)
            unbind(box)
            mode = box.state('MODE')
            physical = box.meta_index(500)
            dirty = state_call(box, 'protection_dirty', physical)
            baseline = box.u32(c.spec.SIG + 500 * 4)
            if not dynamic:
                box.m.uc.mem_write(c.spec.STATE + c.spec.OFF['MODE'], struct.pack('<I', 1))
            evictable = state_call(box, 'can_evict', 500)
            actual = box.dsp_bytes(c.DSP_MIN, 32)
            expected = bytes((i * 17 + 39) & 255 for i in range(32)) if foreign else c.wav_pcm(500, c.FRAMES)[:32]
            out.append(dict(id=f'pcm_boot_{"dynamic" if dynamic else "small"}_{"foreign" if foreign else "clean"}',
                            ok=mode == int(dynamic) and seen['injected'] == foreign
                            and bool(baseline) == (not foreign) and dirty == int(foreign)
                            and evictable == int(not foreign) and actual == expected and not box.m.asserts,
                            mode=mode, baseline=baseline, dirty=dirty, evictable=evictable,
                            injection=seen, pcm_matches=actual == expected, asserts=box.m.asserts))
    for frames in (1, 15, 17):
        samples = {500: ('short', frames), **c.small(range(501, 507))}
        box = c.Box(payload, None, samples, [500], cap=0x40000, record_dsp=True)
        unbind(box)
        row = box.meta_index(500)
        base, _ = box.extent(500)
        baseline = box.u32(c.spec.SIG + 500 * 4)
        dirty = state_call(box, 'protection_dirty', row)
        evictable = state_call(box, 'can_evict', 500)
        expected = c.wav_pcm(500, frames)
        out.append(dict(id=f'pcm_boot_short_sample_{frames}',
                        ok=box.state('MODE') == 1 and baseline != 0 and dirty == 0 and evictable == 1
                        and box.dsp_bytes(base, len(expected)) == expected and not box.m.asserts,
                        baseline=baseline, dirty=dirty, evictable=evictable, asserts=box.m.asserts))
    return out



def pcm_edge_cases(payload):
    from unicorn import arm_const as R
    import sample_swap_io as io
    out = []
    for words in (16, 17, 0x10010):
        box = c.Box(payload, None, c.small(range(500, 506)), [500, 501],
                    cap=0x40000, record_dsp=True)
        unbind(box)
        original = library(box, payload)
        first, size = box.extent(500)
        next_base, _ = box.extent(501)
        first_row, next_row = box.meta_index(500), box.meta_index(501)
        source = 0xC100B000
        box.m.uc.mem_write(source, bytes((i * 19 + 23) & 255 for i in range(128)))
        revision = box.u32(c.spec.PROTECTION_REV)
        for zero in (0, 1, 15):
            box.dev.call(0xC0014284, first, source, zero)
        noops = box.u32(c.spec.PROTECTION_REV) == revision
        box.dev.call(0xC0014284, first + size - 32, source, words)
        flags = [state_call(box, 'protection_dirty', row) for row in (first_row, next_row)]
        out.append(dict(id=f'pcm_native_adjacent_span_{words}',
                        ok=noops and next_base == first + size
                        and flags == [1, int(words == 17)] and library(box, payload) == original
                        and not box.m.asserts, flags=flags, noops=noops, asserts=box.m.asserts))

    box = c.Box(payload, None, c.small(range(500, 506)), [500], cap=0x40000, record_dsp=True)
    unbind(box)
    original = library(box, payload)
    base, _ = box.extent(500)
    physical = box.meta_index(500)
    source = 0xC100B000
    box.m.uc.mem_write(source, bytes((i * 29 + 7) & 255 for i in range(64)))
    read, write = box.m.read, box.m.write
    data_words = [0]

    def stalled(address):
        return 2 if address == io.GPIO and data_words[0] >= 16 else read(address)

    def written(address, value):
        transfer = box.m.dsp_xfer
        if address == c.DSP_DATA and transfer and transfer[0] == 0xAB and transfer[2] > 0:
            data_words[0] += 1
        return write(address, value)

    box.m.read, box.m.write = stalled, written
    status = box.dev.call(0xC0014284, base, source, 32)
    flag = state_call(box, 'protection_dirty', physical)
    out.append(dict(id='pcm_partial_timeout_keeps_sticky_protection',
                    ok=status == 4 and box.state('TSTATE') == 2 and 0 < data_words[0] < 32
                    and flag == 1 and library(box, payload) == original and not box.m.asserts,
                    status=status, fault=box.state('TSTATE'), written=data_words[0], dirty=flag,
                    asserts=box.m.asserts))

    box = c.Box(payload, None, c.small(range(500, 506)), [500, 501], cap=0x40000, record_dsp=True)
    unbind(box)
    base, size = box.extent(500)
    old, current = box.meta_index(500), box.meta_index(501)
    seen = []

    def relocate(uc, *_):
        sp = uc.reg_read(R.UC_ARM_REG_SP)
        if seen or box.u32(sp + 4) != 0xC00142D8:
            return
        seen.append(True)
        uc.mem_write(c.META + old * 0x45C + 11, b'\0')
        uc.mem_write(c.META + current * 0x45C, struct.pack('<II', base, size))

    box.m.uc.hook_add(unicorn.UC_HOOK_CODE, relocate,
                     begin=box.sym['native_scope_acquired'], end=box.sym['native_scope_acquired'])
    box.m.uc.mem_write(source, bytes(range(64)))
    box.dev.call(0xC0014284, base, source, 32)
    flags = [state_call(box, 'protection_dirty', row) for row in (old, current)]
    out.append(dict(id='pcm_range_uses_placement_after_resource_wait',
                    ok=seen == [True] and flags == [0, 1] and not box.m.asserts,
                    relocation_is_model=True, flags=flags, acquired=seen, asserts=box.m.asserts))
    for words in (17, 0):
        box = c.Box(payload, None, {500: ('first', 32), 501: ('next', 32)},
                    [500, 501], cap=0x40000, record_dsp=True)
        unbind(box)
        first, size = box.extent(500)
        second, _ = box.extent(501)
        destination = first + 30
        actual = []
        write = box.m.write

        def observed(address, value):
            transfer = box.m.dsp_xfer
            if address == c.DSP_DATA and transfer and transfer[0] == 0xAB and transfer[2] > 0:
                actual.append(transfer[1])
            return write(address, value)

        box.m.write = observed
        box.m.uc.mem_write(0xC100B000, bytes(range(64)))
        origin = 0xC100C000
        code = f"""push {{r4, lr}}
        sub sp, sp, #8
        mov r0, #1
        bl 0xC0000D80
        mov r4, #2
        str r4, [sp]
        ldr r0, =0x60000000
        ldr r1, ={destination}
        ldr r2, =0xC100B000
        mov r3, #{words}
        bl 0xC00146B4
        mov r0, #1
        bl 0xC0000CA8
        add sp, sp, #8
        pop {{r4, pc}}
        .pool"""
        box.m.uc.mem_write(origin, arm.assemble(code, origin=origin).bytes)
        box.dev.call(origin)
        flags = [state_call(box, 'protection_dirty', box.meta_index(slot)) for slot in (500, 501)]
        out.append(dict(id=f'pcm_leaf_exact_count_{words}',
                        ok=second == first + size and actual == list(range(destination, destination + words * 2, 2))
                        and flags == [int(words != 0), 0] and not box.m.asserts,
                        actual_words=len(actual), next_sample_untouched=not actual or max(actual) + 2 == second,
                        flags=flags, asserts=box.m.asserts))
    return out


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
    out.extend(pcm_write_cases(payload))
    out.extend(pcm_boot_cases(payload))
    out.extend(pcm_edge_cases(payload))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', required=True, type=Path)
    parser.add_argument('--pcm-write', action='store_true', help='probe PCM-only native writes separately')
    parser.add_argument('--pcm-boot', action='store_true', help='check clean and foreign-written parser baselines')
    parser.add_argument('--pcm-edges', action='store_true', help='check native spans, partial writes and acquired placements')
    args = parser.parse_args()
    report = (pcm_write_cases if args.pcm_write else pcm_boot_cases if args.pcm_boot else pcm_edge_cases if args.pcm_edges else cases)(args.patched.read_bytes()[256:])
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report and all(row['ok'] for row in report) else 1)
