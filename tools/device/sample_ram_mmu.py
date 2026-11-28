"""Read ARM926 MMU context without changing MMU or data cache configuration.

CPU capture uses the first KiB of the existing scratch window, then restores it.
A physical TTBR is never treated as a virtual pointer automatically. Table reads
need an explicit virtual alias in known RAM. Candidates do not prove active TLB state,
memory ownership, or DMA safety. An unconfirmed EXEC requires a power cycle.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import sample_ram_canary as probe

TABLE_BYTES = 0x4000


def virtual_base(address):
    if (not isinstance(address, int) or address & (TABLE_BYTES - 1)
            or not (0xC0000000 <= address <= 0xC4000000 - TABLE_BYTES
                    or probe.TABLE_START <= address <= probe.TABLE_END - TABLE_BYTES)):
        raise ValueError('an aligned virtual table alias within known RAM is required')
    return address


def descriptor(word, start, end, domains):
    row = dict(start=start, end=end, descriptor=word, kind=('fault', 'coarse', 'section', 'fine')[word & 3],
               resolved=False)
    if row['kind'] != 'section':
        return row
    if word & 0xFF200 or not word & 0x10:
        row['kind'] = 'invalid_section'
        return row
    physical = (word & 0xFFF00000) + (start & 0xFFFFF)
    domain = word >> 5 & 15
    cacheable, buffered = bool(word & 8), bool(word & 4)
    policy = ('uncached_unbuffered', 'uncached_buffered', 'write_through', 'write_back')[(word >> 2) & 3]
    row.update(resolved=True, physical_start=physical, physical_end=physical + end - start,
               identity=physical == start, cacheable=cacheable, bufferable=buffered,
               domain=domain, domain_access=('no_access', 'client', 'reserved', 'manager')[(domains >> (domain * 2)) & 3],
               ap=word >> 10 & 3, policy=policy)
    return row


def decode_table(table, table_virtual, cpu):
    virtual_base(table_virtual)
    if (cpu['cpu_id'] >> 4) & 0xFFF != 0x926:
        raise ValueError('only ARM926 descriptors are supported')
    if len(table) != TABLE_BYTES:
        raise ValueError('a first-level table has 16 KiB')
    domains = cpu['domain_control']
    own_word = struct.unpack_from('<I', table, (table_virtual >> 20) * 4)[0]
    own = descriptor(own_word, table_virtual, table_virtual + TABLE_BYTES, domains)
    def regions(first, limit):
        rows, start = [], first
        while start < limit:
            end = min(limit, ((start >> 20) + 1) << 20)
            word = struct.unpack_from('<I', table, (start >> 20) * 4)[0]
            rows.append(descriptor(word, start, end, domains))
            start = end
        return rows
    target = regions(probe.START, probe.END)
    mirror = regions(probe.START + 0x4000000, probe.END + 0x4000000)
    matches = all(a['resolved'] and b['resolved'] and a['physical_start'] == b['physical_start']
                  and a['physical_end'] == b['physical_end'] for a, b in zip(target, mirror))
    return dict(status='candidate', table_virtual=table_virtual, table_physical=cpu['ttbr'] & 0xFFFFC000,
                sha256=hashlib.sha256(table).hexdigest(),
                table_alias_consistent=own.get('physical_start') == cpu['ttbr'] & 0xFFFFC000,
                effective_mapping_proven=False, regions=target, mirror_regions=mirror,
                mirror_matches_target=matches)


def inspect_layout(link, cpu, table_virtual, vsb=None, emit=lambda row: None, restored=lambda value: None):
    if table_virtual is None:
        return dict(status='not_read', table_physical=cpu['ttbr'] & 0xFFFFC000,
                    effective_mapping_proven=False)
    virtual_base(table_virtual)
    if not cpu['control'] & 1:
        return dict(status='mmu_disabled', effective_mapping_proven=False)
    def snapshot():
        probe.quiescent(link)
        if not probe.TABLE_START <= table_virtual < probe.TABLE_END:
            return link.read(table_virtual, TABLE_BYTES)
        if vsb is None or table_virtual != cpu['ttbr'] & 0xFFFFC000:
            raise ValueError('SRAM table needs its own original and the verified identity alias')
        parts = []
        restored(False)
        def record(row):
            if row.get('operation') != 'table' or row.get('start') != table_virtual + sum(map(len, parts)):
                raise ValueError('SRAM table parts are not contiguous')
            data = row['data']
            if len(data) != row['end'] - row['start'] or len(data) > probe.MAP_BYTES:
                raise ValueError('SRAM table part length differs')
            parts.append(data)
            emit({key: value for key, value in row.items() if key != 'data'})
        probe.measure(link, vsb, 'table', record, lambda: restored(True),
                      span=(table_virtual, table_virtual + TABLE_BYTES))
        data = b''.join(parts)
        if len(data) != TABLE_BYTES:
            raise ValueError('SRAM table snapshot is incomplete')
        return data
    first = snapshot()
    second = snapshot()
    probe.quiescent(link)
    if first != second:
        raise ValueError('translation table changed during the snapshot')
    return decode_table(first, table_virtual, cpu)


def stable_registers(cpu):
    return {**cpu, 'ttbr': cpu['ttbr'] & 0xFFFFC000, 'fcse': cpu['fcse'] & 0xFE000000}


def diagnose(link, vsb, table_virtual=None, emit=lambda row: None, restored=lambda value: None):
    def capture():
        rows = []
        restored(False)
        def record(row):
            rows.append(row)
            emit(row)
        probe.measure(link, vsb, 'info', record, lambda: restored(True))
        if len(rows) != 1 or rows[0].get('operation') != 'info':
            raise ValueError('CPU snapshot is incomplete')
        return rows[0]
    before = capture()
    layout = inspect_layout(link, before, table_virtual, vsb, emit, restored)
    after = capture() if table_virtual is not None else before
    if stable_registers(before) != stable_registers(after):
        raise ValueError('CPU registers changed during the snapshot')
    return dict(cpu=before, cpu_after=after, layout=layout, effective_mapping_proven=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--port-idle-confirmed', action='store_true')
    parser.add_argument('--stopped-main-confirmed', action='store_true')
    parser.add_argument('--table-virtual-base', type=lambda value: int(value, 0))
    parser.add_argument('--vsb', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(dict(hardware_contact=False, configuration_writes=False, automatic_table_read=False,
                              scratch='first KiB only, restored after each confirmed EXEC',
                              baseline='fresh minimal BLECH SysEx build',
                              table='explicit virtual alias derived from firmware required',
                              limitation='a candidate is not proof of active mappings or free RAM'), indent=2))
        return 0
    if not (args.port_idle_confirmed and args.stopped_main_confirmed and args.vsb and args.json):
        raise ValueError('execution needs own original, external report, exclusive port and STOP/main')
    if args.table_virtual_base is not None:
        virtual_base(args.table_virtual_base)
    output = args.json.resolve()
    if any((part / '.git').exists() for part in (output, *output.parents)):
        raise ValueError('report must be outside a repository')
    vsb = args.vsb.read_bytes()
    report = dict(hardware_contact=False, configuration_writes=False, card_writes=False,
                  flash_writes=False, dsp_writes=False, scratch_restored=False,
                  upper_virtual_range_written=False, proves_free_ram=False,
                  effective_mapping_proven=False, observations=[], error=None)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        def save():
            file.seek(0)
            file.truncate()
            json.dump(report, file, indent=2)
            file.flush()
        def emit(row):
            report['observations'].append(row)
            save()
        def restored(value):
            report['scratch_restored'] = value
            save()
        save()
        try:
            from blue_report import midi_ask, search
            report['hardware_contact'] = True
            ask, _ = midi_ask()
            device = search(ask)
            if device['model'] != 0x24 or device['version'] != '2.02':
                raise ValueError('red Sampler 2.02 required')
            report.update(diagnose(probe.Link(ask, device['channel'], device['model']), vsb,
                                   args.table_virtual_base, emit, restored))
        except BaseException as error:
            report['error'] = str(error)
        save()
    print(json.dumps(dict(complete=report['error'] is None, scratch_restored=report['scratch_restored'],
                          report=str(output))))
    return 1 if report['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
