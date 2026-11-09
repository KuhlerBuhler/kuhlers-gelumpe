"""Exercise register capture over BLECH SysEx with generated ARM926 tables.

CP15 reads and the scratch mirror are injected, not hardware translation.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

import unicorn
from unicorn import arm_const as registers

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'device'))
from led_show import emulator_ask
from blue_report import search
import sample_ram_canary as probe
import sample_ram_mmu as mmu

KINDS = ('registers', 'table', 'uncertain_second', 'sram', 'sram_uncertain',
         'sram_uncertain_late', 'stale_code', 'cached_fill_refused')


def case(base, patched, kind, writeback_cache=False):
    ask, machine = emulator_ask(patched)
    device = search(ask)
    values = {0xEE116F10: 0x5107D, 0xEE126F10: 0xC200003F,
              0xEE136F10: 0xFFFFFFFF, 0xEE1D6F10: 0x02000000,
              0xEE106F10: 0x41069265, 0xEE106F30: 0x1D112152,
              0xEE196F11: 0xA, 0xEE196F31: 0x1000C}
    captures, calls, touched, spoiled = [], [], [], []
    table_base = 0x8001C000 if kind.startswith('sram') else 0xC2000000
    values[0xEE126F10] = table_base | 0x3F
    table = bytearray(0x4000)
    for index in range(0xC00, 0xC40):
        struct.pack_into('<I', table, index * 4, index << 20 | 0xC12)
    if kind.startswith('sram'):
        struct.pack_into('<I', table, 0x800 * 4, 0x80000C1E)
        for index in range(0xC00, 0xC40):
            struct.pack_into('<I', table, index * 4, index << 20 | 0xC1E)
            struct.pack_into('<I', table, (index + 0x40) * 4, index << 20 | 0xC12)
    machine.uc.mem_write(table_base, bytes(table))
    original = bytes(machine.uc.mem_read(probe.STUB, 1024))
    machine.uc.mem_write(probe.STUB + 0x4000000, original)

    pending, maintenance = {}, []

    def scratch_mirror(uc, access, address, size, value, _):
        if not writeback_cache and (kind != 'stale_code' or address >= probe.RESULT):
            uc.mem_write(address + 0x4000000, (value & ((1 << (size*8))-1)).to_bytes(size, 'little'))

    machine.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, scratch_mirror,
                        begin=probe.STUB, end=probe.STUB + 1023)

    def publication(uc, address, size, _):
        word = struct.unpack('<I', uc.mem_read(address, 4))[0]
        if word == 0xEE110F10:
            uc.reg_write(registers.UC_ARM_REG_R0, 0x5107D)
            uc.reg_write(registers.UC_ARM_REG_PC, address + 4)
        elif word == 0xEE070F3A:
            line = uc.reg_read(registers.UC_ARM_REG_R0)
            if not probe.STUB <= line <= probe.STUB + 1024 - 32 or line & 31:
                raise RuntimeError('cache clean outside EXEC scratch')
            pending[line] = bytes(uc.mem_read(line, 32))
            maintenance.append(('clean', line))
            uc.reg_write(registers.UC_ARM_REG_PC, address + 4)
        elif word == 0xEE070F9A:
            for line, data in pending.items():
                if kind != 'stale_code' or line >= probe.RESULT:
                    uc.mem_write(line + 0x4000000, data)
            pending.clear()
            maintenance.append(('drain', 0))
            uc.reg_write(registers.UC_ARM_REG_PC, address + 4)

    if writeback_cache:
        for start, end in ((0xC0172100, 0xC0173000), (0xC017B950, 0xC017C190)):
            machine.uc.hook_add(unicorn.UC_HOOK_CODE, publication, begin=start, end=end - 1)

    def cp15(uc, address, size, _):
        word = struct.unpack('<I', uc.mem_read(address, 4))[0]
        if word in values:
            if word == 0xEE116F10:
                captures.append(address)
            uc.reg_write(registers.UC_ARM_REG_R6, values[word])
            uc.reg_write(registers.UC_ARM_REG_PC, address + 4)

    def completion(uc, access, address, size, value, _):
        uncertain = kind in ('uncertain_second', 'sram_uncertain', 'sram_uncertain_late')
        fail_after = 10 if kind == 'sram_uncertain_late' else 2
        if uncertain and len(captures) == fail_after and address == probe.RESULT and value == probe.MAGIC:
            nonce = struct.unpack('<I', uc.mem_read(probe.RESULT + 4, 4))[0]
            uc.mem_write(probe.RESULT + 4, struct.pack('<I', nonce ^ 1))
            spoiled.append(len(calls))

    machine.uc.hook_add(unicorn.UC_HOOK_CODE, cp15, begin=probe.STUB, end=probe.RESULT - 4)
    machine.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, completion, begin=probe.RESULT, end=probe.RESULT + 3)
    machine.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                        lambda uc, access, address, size, value, _: touched.append(address),
                        begin=probe.START, end=probe.END - 1)
    def recorded(message):
        calls.append(message[6])
        return ask(message)
    states, rows, error, result = [], [], None, None
    try:
        link = probe.Link(recorded, device['channel'], device['model'])
        if kind == 'cached_fill_refused':
            states.append(False)
            probe.measure(link, Path(base).read_bytes(), 'fill', rows.append, lambda: states.append(True))
        else:
            result = mmu.diagnose(link, Path(base).read_bytes(), None if kind == 'registers' else table_base,
                                  rows.append, states.append)
    except (RuntimeError, ValueError) as failure:
        error = str(failure)
    unchanged = bytes(machine.uc.mem_read(probe.STUB, 1024)) == original
    physical_unchanged = bytes(machine.uc.mem_read(probe.STUB + 0x4000000, 1024)) == original
    if kind == 'stale_code':
        ok = ('uncached' in (error or '') and 'EXEC not sent' in error and not captures
              and 0x6F not in calls and states == [False] and not unchanged)
    elif kind == 'cached_fill_refused':
        ok = ('refused' in (error or '') and unchanged and states == [False, True]
              and len(rows) == 1 and rows[0]['status'] == 1)
    elif kind in ('uncertain_second', 'sram_uncertain', 'sram_uncertain_late'):
        ok = ('unconfirmed' in (error or '') and states == [False, True, False]
              and spoiled and calls[spoiled[0]:] == [0x61] and not unchanged)
    else:
        layout = result['layout'] if result else {}
        ok = (error is None and unchanged and physical_unchanged and states[-1] and result['cpu']['control'] == 0x5107D
              and not result['effective_mapping_proven']
              and layout['status'] == ('not_read' if kind == 'registers' else 'candidate'))
        if kind in ('table', 'sram'):
            ok = ok and layout['table_alias_consistent'] and len(layout['regions']) == 25
        if kind == 'sram':
            ok = ok and layout['mirror_matches_target'] and all(row['policy'] == 'uncached_unbuffered' for row in layout['mirror_regions'])
    source_unchanged = bytes(machine.uc.mem_read(table_base, len(table))) == bytes(table)
    return dict(id=kind, ok=bool(ok and source_unchanged and not touched and not machine.asserts),
                cp15_captures=len(captures), scratch_unchanged=unchanged, restoration=states,
                physical_scratch_unchanged=physical_unchanged, cache_maintenance=len(maintenance),
                source_unchanged=source_unchanged, upper_virtual_writes=len(touched), error=error, asserts=machine.asserts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--only', choices=KINDS)
    parser.add_argument('--writeback-cache', action='store_true')
    args = parser.parse_args()
    results = [case(args.base, args.patched, kind, args.writeback_cache) for kind in ((args.only,) if args.only else KINDS)]
    print(json.dumps(dict(hardware_contact=False, cp15_injected=True, scratch_mirror_injected=True, translation_modelled=False,
                          writeback_cache_injected=args.writeback_cache,
                          results=results), indent=2))
    return 0 if all(row['ok'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
