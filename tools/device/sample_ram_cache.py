"""Bounded cache-aware upper-RAM observations, offline unless explicitly executed.

Seeding overwrites the upper arena on a test device. Checks observe physical
memory before cached memory, without cleaning either view. Canaries do not
prove ownership or DMA safety. An unconfirmed EXEC stops all communication.
"""
import argparse
import json
import secrets
from pathlib import Path

import sample_ram_canary as probe
import sample_ram_mmu as mmu

ALIAS, CHUNK = 0x04000000, 65536


def build(operation, start, end, seed, nonce):
    if (operation not in ('seed', 'check') or not probe.START <= start < end <= probe.END
            or (start | end) & 4095 or end - start > CHUNK
            or not 0 < seed <= 0xFFFFFFFF or not 0 < nonce <= 0xFFFFFFFF):
        raise ValueError('an aligned upper-RAM chunk up to 64 KiB and nonzero seed/token are required')
    pages = (end - start) // 4096
    read_pass = '''physical_page:
    mov r10, #0
    add r11, r5, #4096
physical_word:
    ldr r0, [r5, r12]
    eor r1, r5, r7
    cmp r0, r1
    addne r10, r10, #1
    add r5, r5, #4
    cmp r5, r11
    blo physical_word
    cmp r10, #255
    movhi r10, #255
    strb r10, [r8], #1
    cmp r10, #0
    addne r9, r9, #1
    cmp r5, r6
    blo physical_page
    str r9, [r4, #24]
'''
    if operation == 'seed':
        body = f'''seed_word:
    eor r0, r5, r7
    str r0, [r5], #4
    cmp r5, r6
    blo seed_word
    ldr r0, ={start}
clean_line:
    .word 0xEE070F3A
    add r0, r0, #32
    cmp r0, r6
    blo clean_line
    mov r0, #0
    .word 0xEE070F9A
    ldr r5, ={start}
{read_pass}
    mov r0, #5
    cmp r9, #0
    bne finish
'''
    else:
        body = f'''{read_pass}
    ldr r5, ={start}
    mov r9, #0
cached_page:
    mov r10, #0
    mov r3, #0
    add r11, r5, #4096
cached_word:
    ldr r2, [r5, r12]
    ldr r0, [r5]
    cmp r0, r2
    addne r3, r3, #1
    eor r1, r5, r7
    cmp r0, r1
    addne r10, r10, #1
    add r5, r5, #4
    cmp r5, r11
    blo cached_word
    cmp r10, #255
    movhi r10, #255
    strb r10, [r8]
    cmp r3, #255
    movhi r3, #255
    strb r3, [r8, #{pages}]
    add r8, r8, #1
    cmp r10, #0
    addne r9, r9, #1
    cmp r5, r6
    blo cached_page
    str r9, [r4, #28]
'''
    source = f'''.org {probe.STUB}
entry:
    push {{r4-r11, r12, lr}}
    ldr r4, ={probe.RESULT}
    ldr r5, ={nonce}
    cmp r0, r5
    bne invalid
    str r5, [r4, #4]
    .word 0xEE116F10
    str r6, [r4, #12]
    ldr r1, =0x5107D
    mov r0, #1
    cmp r6, r1
    bne finish
    .word 0xEE100F10
    lsr r0, r0, #4
    ldr r1, =0xFFF
    and r0, r0, r1
    ldr r1, =0x926
    cmp r0, r1
    bne cpu_refused
    .word 0xEE190F11
    cmp r0, #0x1C
    bne cpu_refused
    .word 0xEE190F31
    cmp r0, #0x1C
    bne cpu_refused
    .word 0xEE120F10
    lsr r0, r0, #14
    lsl r0, r0, #14
    ldr r1, =0x8001C000
    cmp r0, r1
    bne cpu_refused
    .word 0xEE130F10
    cmp r0, #3
    bne cpu_refused
    .word 0xEE1D0F10
    lsr r0, r0, #25
    cmp r0, #0
    bne cpu_refused
{probe.context_guard()}
    ldr r5, ={start}
    str r5, [r4, #16]
    ldr r6, ={end}
    str r6, [r4, #20]
    ldr r7, ={seed}
    ldr r8, ={probe.MAP}
    ldr r12, ={ALIAS}
    mov r9, #0
    str r9, [r4, #24]
    str r9, [r4, #28]
{body}
    mov r0, #0
    b finish
cpu_refused:
    mov r0, #3
finish:
    str r0, [r4, #8]
    ldr r0, ={probe.MAGIC}
    str r0, [r4]
    pop {{r4-r11, r12, pc}}
invalid:
    mov r0, #0
    pop {{r4-r11, r12, pc}}
    .pool
'''
    result = probe.arm.assemble(source, origin=probe.STUB)
    if len(result.bytes) > probe.RESULT - probe.STUB:
        raise ValueError('cache probe code overlaps its result')
    return result.bytes, result.symbols


def baseline(vsb, patch):
    build = probe.sample_swap_io.validate_firmware(vsb)
    if (build not in ('stock', 'hacktribe') or patch.get('format') != 'gelumpe-patch'
            or patch.get('id') != 'blech-sysex' or patch.get('builds') != [build]
            or len(patch.get('changes', [])) != 5):
        raise ValueError('the current minimal red SysEx build and its patch are required')
    changes = []
    for row in patch['changes']:
        at, data = row['file'], bytes.fromhex(row['bytes'])
        if not isinstance(at, int) or at < 0x100 or not data or at + len(data) > len(vsb) or vsb[at:at+len(data)] != data:
            raise ValueError('SysEx patch does not match the supplied minimal VSB')
        changes.append((at - 0x100 + 0xC0000000, data))
    if not any(bytes.fromhex('3a0f07ee') in data for _, data in changes):
        raise ValueError('EXEC upload publication fix is required')
    return changes


def preflight_backend(link, vsb, patch):
    changes = baseline(vsb, patch)
    link.info()
    for address, data in changes:
        if link.read(address, len(data)) != data:
            raise ValueError(f'new SysEx backend differs at {address:#x}; no RAM seed permitted')
    probe.preflight(link, vsb)


def validate_mapping(report):
    cpu, after, layout = report['cpu'], report['cpu_after'], report['layout']
    if (mmu.stable_registers(cpu) != mmu.stable_registers(after)
            or cpu['control'] != 0x5107D or cpu['ttbr'] & 0xFFFFC000 != 0x8001C000
            or cpu['dtcm_region'] != 0x1C or cpu['itcm_region'] != 0x1C
            or cpu['domain_control'] != 3 or cpu['fcse'] & 0xFE000000
            or cpu['cpu_id'] >> 4 & 0xFFF != 0x926
            or layout.get('status') != 'candidate' or not layout.get('table_alias_consistent')
            or not layout.get('mirror_matches_target')):
        raise ValueError('CPU context or stable table candidate differs')
    cached, physical = layout['regions'], layout['mirror_regions']
    cursor = probe.START
    if len(cached) != len(physical):
        raise ValueError('incomplete cache/mirror mapping')
    for a, b in zip(cached, physical):
        end = min(probe.END, ((cursor >> 20) + 1) << 20)
        if (not a.get('resolved') or not b.get('resolved') or a['start'] != cursor or a['end'] != end
                or b['start'] != cursor + ALIAS or b['end'] != end + ALIAS
                or a['physical_start'] != cursor or b['physical_start'] != cursor
                or a['physical_end'] != end or b['physical_end'] != end
                or a['policy'] != 'write_back' or b['policy'] != 'uncached_unbuffered'
                or any(row['domain'] != 0 or row['domain_access'] != 'manager' or row['ap'] != 3 for row in (a, b))):
            raise ValueError('upper RAM or physical mirror descriptor differs')
        cursor = end
    if cursor != probe.END:
        raise ValueError('incomplete upper RAM mapping')


def measure(link, vsb, patch, operation, seed, emit, restored, start=probe.START, end=probe.END):
    if not probe.START <= start < end <= probe.END or (start | end) & 4095:
        raise ValueError('only complete pages in the upper arena are permitted')
    build(operation, start, min(end, start + CHUNK), seed, 1)
    preflight_backend(link, vsb, patch)
    mapping = mmu.diagnose(link, vsb, 0x8001C000, emit, restored)
    validate_mapping(mapping)
    emit(dict(operation='mapping', cpu=mapping['cpu'], layout=mapping['layout'], proves_free_ram=False))
    probe.quiescent(link)
    backup = link.read(probe.STUB, 1024)
    confirmed = False
    try:
        for first in range(start, end, CHUNK):
            limit = min(end, first + CHUNK)
            nonce = secrets.randbits(32) or 1
            code, _ = build(operation, first, limit, seed, nonce)
            confirmed = False
            restored(False)
            words = probe.execute_code(link, code, nonce)
            confirmed = True
            if words[2] not in (0, 5):
                emit(dict(operation=operation, start=first, end=limit, status=words[2], refused=True))
                raise ValueError('CPU or UI context refused; chunk not accessed')
            pages = (limit - first) // 4096
            if words[4:6] != (first, limit) or max(words[6:]) > pages:
                raise ValueError('chunk completion bounds differ')
            data = link.read(probe.MAP, pages * (3 if operation == 'check' else 1))
            changes = lambda offset: [[first + index * 4096, count] for index, count in enumerate(data[offset:offset+pages]) if count]
            physical = changes(0)
            cached = changes(pages) if operation == 'check' else []
            disagreement = changes(2 * pages) if operation == 'check' else []
            if len(physical) != words[6] or len(cached) != words[7]:
                raise ValueError('page map and completion counts differ')
            emit(dict(operation=operation, start=first, end=limit, status=words[2], seed=seed,
                      physical_changes=physical, cached_changes=cached, view_disagreements=disagreement))
            if words[2]:
                raise ValueError('seed publication verification failed')
            if operation == 'check' and (disagreement or physical != cached):
                raise ValueError('cached and physical views disagree; observation stopped')
    finally:
        if confirmed:
            probe.quiescent(link)
            link.write_at(probe.STUB, backup)
            if link.read(probe.STUB + ALIAS, len(backup)) != backup:
                raise ValueError('scratch physical restoration differs; restart required')
            restored(True)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--ram-overwrite-confirmed', action='store_true')
    parser.add_argument('--port-idle-confirmed', action='store_true')
    parser.add_argument('--stopped-main-confirmed', action='store_true')
    parser.add_argument('--operation', choices=('seed', 'check'))
    parser.add_argument('--seed', type=lambda value: int(value, 0))
    parser.add_argument('--phase')
    parser.add_argument('--vsb', type=Path)
    parser.add_argument('--patch', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args(argv)
    if args.execute:
        if not all((args.ram_overwrite_confirmed, args.port_idle_confirmed, args.stopped_main_confirmed,
                    args.operation, args.seed, args.phase, args.vsb, args.patch, args.json)):
            raise ValueError('execution requires all confirmations, seed, phase, minimal VSB, patch and external report')
        if len(args.phase) > 64 or any(ord(char) < 32 for char in args.phase):
            raise ValueError('phase must be a short printable label')
        build(args.operation, probe.START, probe.START + CHUNK, args.seed, 1)
    return args


def main(argv=None):
    args = arguments(argv)
    if not args.execute:
        print(json.dumps(dict(hardware_contact=False, configuration_writes=False, proves_free_ram=False,
                              start=probe.START, end=probe.END, mirror_offset=ALIAS, chunk=CHUNK,
                              next='explicitly approved mode sequence on a backed-up test card')))
        return 0
    output = args.json.resolve()
    if any((part / '.git').exists() for part in (output, *output.parents)):
        raise ValueError('measurement report must be outside a repository')
    vsb, patch = args.vsb.read_bytes(), json.loads(args.patch.read_text())
    baseline(vsb, patch)
    report = dict(hardware_contact=False, configuration_writes=False, flash_writes=False,
                  card_writes=False, dsp_writes=False, proves_free_ram=False, effective_mapping_proven=False,
                  scratch_restored=False, target_ram_restored=False, reboot_required=True,
                  upper_virtual_range_may_be_written=False, operation=args.operation, seed=args.seed,
                  phase=args.phase, observations=[], error=None)
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
                raise ValueError('red Sampler2.02 required')
            report['upper_virtual_range_may_be_written'] = args.operation == 'seed'
            measure(probe.Link(ask, device['channel'], device['model']), vsb, patch,
                    args.operation, args.seed, emit, restored)
        except BaseException as error:
            report['error'] = str(error)
        save()
    print(json.dumps(dict(complete=report['error'] is None, scratch_restored=report['scratch_restored'], report=str(output))))
    return 1 if report['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
