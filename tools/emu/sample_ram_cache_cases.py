"""Native SysEx cache-probe cases with injected CP15/cache views, no hardware."""
import argparse
import json
import struct
import sys
from pathlib import Path

import unicorn
from unicorn import arm_const as R

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'device'))
from led_show import emulator_ask
from blue_report import search
import sample_ram_canary as probe
import sample_ram_cache as cache


class Model:
    def __init__(self, patched, late=False):
        self.ask_native, self.machine = emulator_ask(patched)
        device = search(self.ask_native)
        self.link = probe.Link(self.ask, device['channel'], device['model'])
        self.original = bytes(self.machine.uc.mem_read(probe.STUB, 1024))
        self.machine.uc.mem_write(probe.STUB + cache.ALIAS, self.original)
        table = bytearray(0x4000)
        for index in range(0xC00, 0xC40):
            struct.pack_into('<I', table, index * 4, index << 20 | 0xC1E)
            struct.pack_into('<I', table, (index + 0x40) * 4, index << 20 | 0xC12)
        struct.pack_into('<I', table, 0x800 * 4, 0x80000C1E)
        self.machine.uc.mem_write(0x8001C000, bytes(table))
        self.pending, self.calls, self.clean_upper, self.spoiled = {}, [], [], []
        self.values = {0xEE110F10: 0x5107D, 0xEE100F10: 0x41069265, 0xEE120F10: 0x8001C000,
                       0xEE130F10: 3, 0xEE1D0F10: 0, 0xEE100F30: 0x1D152152,
                       0xEE190F11: 0x1C, 0xEE190F31: 0x1C}
        for lo, hi in ((probe.STUB, probe.RESULT), (0xC0172100, 0xC0173000), (0xC017B950, 0xC017C190)):
            self.machine.uc.hook_add(unicorn.UC_HOOK_CODE, self.cp15, begin=lo, end=hi - 1)
        if late:
            self.machine.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, self.spoil, begin=probe.RESULT, end=probe.RESULT + 3)

    def ask(self, message):
        self.calls.append(message[6])
        return self.ask_native(message)

    def cp15(self, uc, address, size, _):
        word = struct.unpack('<I', uc.mem_read(address, 4))[0]
        base = word & ~0xF000
        if base in self.values:
            uc.reg_write(R.UC_ARM_REG_R0 + (word >> 12 & 15), self.values[base])
        elif word == 0xEE070F3A:
            line = uc.reg_read(R.UC_ARM_REG_R0)
            scratch = probe.STUB <= line <= probe.STUB + 1024 - 32
            upper = probe.START <= line <= probe.START + 2 * cache.CHUNK - 32
            if not (scratch or upper) or line & 31:
                raise RuntimeError('cache operation outside modelled ranges')
            self.pending[line] = bytes(uc.mem_read(line, 32))
            if upper:
                self.clean_upper.append(line)
        elif word == 0xEE070F9A:
            for line, data in self.pending.items():
                uc.mem_write(line + cache.ALIAS, data)
            self.pending.clear()
        else:
            return
        uc.reg_write(R.UC_ARM_REG_PC, address + 4)

    def spoil(self, uc, access, address, size, value, _):
        start = struct.unpack('<I', uc.mem_read(probe.RESULT + 16, 4))[0]
        if value == probe.MAGIC and start == probe.START + cache.CHUNK:
            nonce = struct.unpack('<I', uc.mem_read(probe.RESULT + 4, 4))[0]
            uc.mem_write(probe.RESULT + 4, struct.pack('<I', nonce ^ 1))
            self.spoiled.append(len(self.calls))

    def intact(self):
        return all(bytes(self.machine.uc.mem_read(address, 1024)) == self.original
                   for address in (probe.STUB, probe.STUB + cache.ALIAS))


def case(vsb, patch, kind):
    model = Model(vsb, kind == 'uncertain_late')
    rows, states, error = [], [], None
    end = probe.START + (2 * cache.CHUNK if kind == 'uncertain_late' else 8192)
    try:
        cache.measure(model.link, Path(vsb).read_bytes(), json.loads(Path(patch).read_text()),
                      'seed', 77, rows.append, states.append, start=probe.START, end=end)
    except (ValueError, RuntimeError) as failure:
        error = str(failure)
    if kind == 'uncertain_late':
        ok = (error and 'unconfirmed' in error and states[-1] is False and not model.intact()
              and model.spoiled and model.calls[model.spoiled[0]:] == [0x61]
              and len([r for r in rows if r['operation'] == 'seed']) == 1)
        return dict(id=kind, ok=bool(ok and not model.machine.asserts), error=error, restoration=states,
                    asserts=model.machine.asserts, seeded_chunks=1)
    seeded = bytes(model.machine.uc.mem_read(probe.START, 8192))
    physical = bytes(model.machine.uc.mem_read(probe.START + cache.ALIAS, 8192))
    seed_ok = error is None and model.intact() and seeded == physical and states[-1] is True
    before_clean = len(model.clean_upper)
    code, _ = cache.build('check', probe.START, end, 77, 123)
    good = probe.execute_code(model.link, code, 123)
    clean_map = bytes(model.machine.uc.mem_read(probe.MAP, 6))
    model.machine.uc.mem_write(probe.START + cache.ALIAS + 4, b'DMA!')
    model.machine.uc.mem_write(probe.START + 4096 + 8, b'CPU!')
    changed = probe.execute_code(model.link, code, 123)
    maps = bytes(model.machine.uc.mem_read(probe.MAP, 6))
    model.link.write_at(probe.STUB, model.original)
    ok = (seed_ok and good[2] == 0 and good[6:] == (0, 0) and clean_map == bytes(6)
          and changed[6:] == (1, 1) and maps == bytes([1, 0, 0, 1, 1, 1])
          and len(model.clean_upper) == before_clean and model.intact() and not model.machine.asserts)
    return dict(id=kind, ok=bool(ok), seed_error=error, scratch_restored=model.intact(),
                upper_clean_lines=before_clean, check_clean_lines=len(model.clean_upper) - before_clean,
                changed_maps=list(maps), asserts=model.machine.asserts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--patch', type=Path, required=True)
    parser.add_argument('--only', choices=('views', 'uncertain_late'))
    args = parser.parse_args()
    results = [case(args.patched, args.patch, kind) for kind in ((args.only,) if args.only else ('views', 'uncertain_late'))]
    print(json.dumps(dict(hardware_contact=False, cp15_injected=True, cache_views_injected=True,
                          translation_modelled=False, dma_modelled=False, results=results), indent=2))
    return 0 if all(row['ok'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
