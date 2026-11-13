"""Observe writes to the upper RAM on a red Sampler without installing a cache.

Offline by default. Execution fills only 0xC274F000..0xC4000000, outside the
work buffer and both stacks. A fresh original with only BLECH SysEx is required.
Each invocation runs once at STOP on the main page and restores scratch RAM
before the next mode operation; power cycle after the observation. Card and DSP
APIs are never called. An unconfirmed EXEC stops without retry or cleanup.
Unchanged canaries alone do not prove that RAM has no owner or future reader.
"""
import argparse
import json
import secrets
import struct
from pathlib import Path

from sample_swap_paths import Link, arm, old
import sample_swap_io

STUB, MAGIC = old.STUB, old.MAGIC
RESULT, MAP, MAP_BYTES = STUB + 0x300, STUB + 0x320, 224
START, END, KEY = 0xC274F000, 0xC4000000, 0x5A5AA5A5
TABLE_START, TABLE_END, TABLE_BYTES = 0x80000000, 0x80020000, 0x4000
SCREENS, TRANSPORT = 0xC03404C0, 0xC03405BC
SPANS = ((0xC00364F4, 4), (0xC00016A4, 0x34), (0xC0030D28, 0x34),
         (0xC004FAF8, 8), (0xC017CC00, 32), (0xC0150300, 32), (0xC014FCF0, 16))


def context_guard():
    return f'''    mov r0, #2
    ldr r1, ={SCREENS}
    ldr r1, [r1]
    ldr r2, =0xC0000000
    cmp r1, r2
    blo finish
    ldr r2, =0xC4000000 - 0x34
    cmp r1, r2
    bhi finish
    ldr r2, [r1, #0x24]
    cmp r2, #0
    bne finish
    ldr r1, [r1, #0x2C]
    cmp r1, #1
    bne finish
    ldr r1, ={TRANSPORT}
    ldr r1, [r1]
    ldr r2, =0xC0000000
    cmp r1, r2
    blo finish
    ldr r2, =0xC4000000 - 0x30C
    cmp r1, r2
    bhi finish
    ldr r1, [r1, #0x308]
    cmp r1, #0
    bne finish
'''


def build(operation, start=START, end=END, nonce=1):
    if operation not in ('fill', 'check', 'info', 'table'):
        raise ValueError('fill, check, info or table required')
    if operation == 'table':
        if (not TABLE_START <= start < end <= TABLE_END or (start | end) & 3
                or end-start > MAP_BYTES or start >> 14 != (end-1) >> 14 or not 0 < nonce <= 0xFFFFFFFF):
            raise ValueError('SRAM table capture exceeds its bounded window')
    elif not START <= start < end <= END or (start | end) & 4095 or not 0 < nonce <= 0xFFFFFFFF:
        raise ValueError('only aligned pages within the upper arena are allowed')
    if operation == 'check' and (end - start) // 4096 > MAP_BYTES:
        raise ValueError('check map exceeds the approved scratch window')
    body = '''fill_word:
    eor r0, r5, r7
    str r0, [r5], #4
    cmp r5, r6
    blo fill_word
''' if operation == 'fill' else '''next_page:
    mov r10, #0
    add r11, r5, #4096
check_word:
    ldr r0, [r5]
    eor r1, r5, r7
    cmp r0, r1
    addne r10, r10, #1
    add r5, r5, #4
    cmp r5, r11
    blo check_word
    cmp r10, #255
    movhi r10, #255
    strb r10, [r8], #1
    cmp r10, #0
    addne r9, r9, #1
    cmp r5, r6
    blo next_page
'''
    cache_guard = '''    mov r0, #1
    tst r6, #5
    bne finish
''' if operation not in ('info', 'table') else ''
    action = f'''    ldr r5, ={start}
    str r5, [r4, #16]
    ldr r6, ={end}
    str r6, [r4, #20]
    ldr r7, ={KEY}
    ldr r8, ={MAP}
    mov r9, #0
{body}
    str r9, [r4, #24]
    ldr r0, ={(end-start)//4096}
    str r0, [r4, #28]
''' if operation != 'info' else '''    .word 0xEE106F10
    str r6, [r4, #28]
    lsr r1, r6, #4
    ldr r2, =0xFFF
    and r1, r1, r2
    ldr r2, =0x926
    mov r0, #3
    cmp r1, r2
    bne finish
    .word 0xEE126F10
    str r6, [r4, #16]
    .word 0xEE136F10
    str r6, [r4, #20]
    .word 0xEE1D6F10
    str r6, [r4, #24]
    .word 0xEE106F30
    str r6, [r4, #32]
    .word 0xEE196F11
    str r6, [r4, #36]
    .word 0xEE196F31
    str r6, [r4, #40]
'''
    if operation == 'table':
        action = f'''    mov r0, #4
    tst r6, #1
    beq finish
    .word 0xEE126F10
    lsr r1, r6, #14
    lsl r1, r1, #14
    str r1, [r4, #28]
    ldr r2, ={start & 0xFFFFC000}
    cmp r1, r2
    bne finish
    ldr r5, ={start}
    str r5, [r4, #16]
    ldr r6, ={end}
    str r6, [r4, #20]
    ldr r8, ={MAP}
table_word:
    ldr r0, [r5], #4
    str r0, [r8], #4
    cmp r5, r6
    blo table_word
    ldr r0, ={end-start}
    str r0, [r4, #24]
'''
    source = f'''
    push {{r4-r11, r12, lr}}
    ldr r4, ={RESULT}
    ldr r5, ={nonce}
    cmp r0, r5
    bne invalid
    str r5, [r4, #4]
read_control:
    .word 0xEE116F10
    str r6, [r4, #12]
{cache_guard}
{context_guard()}
{action}
    mov r0, #0
finish:
    str r0, [r4, #8]
    ldr r0, ={MAGIC}
    str r0, [r4]
    pop {{r4-r11, r12, pc}}
invalid:
    mov r0, #0
    pop {{r4-r11, r12, pc}}
    .pool
'''
    result = arm.assemble(source, origin=STUB)
    if len(result.bytes) > RESULT - STUB:
        raise ValueError('canary code overlaps its result')
    return result.bytes, result.symbols


def invoke(link, operation, start, end, nonce):
    code, _ = build(operation, start, end, nonce)
    return execute_code(link, code, nonce)


def execute_code(link, code, nonce):
    quiescent(link)
    link.write_at(RESULT, bytes(32))
    quiescent(link)
    link.write_at(STUB, code)
    quiescent(link)
    if link.read(STUB + 0x4000000, len(code)) != code:
        raise ValueError('code differs in uncached RAM; EXEC not sent; restart required')
    try:
        link.execute(nonce)
    except BaseException as error:
        raise RuntimeError('EXEC completion unconfirmed; no retry or cleanup; power cycle required') from error
    words = struct.unpack('<8I', link.read(RESULT, 32))
    if words[:2] != (MAGIC, nonce):
        raise RuntimeError('EXEC marker unconfirmed; no retry or cleanup; power cycle required')
    return words


def preflight(link, vsb):
    sample_swap_io.validate_firmware(vsb)
    link.info()
    for address, size in SPANS:
        offset = address - 0xC0000000 + 0x100
        if link.read(address, size) != vsb[offset:offset + size]:
            raise ValueError(f'baseline differs at {address:#x} or sample-swap is installed; no RAM fill permitted')


def quiescent(link):
    def word(address):
        return struct.unpack('<I', link.read(address, 4))[0]
    outer, transport = word(SCREENS), word(TRANSPORT)
    if not 0xC0000000 <= outer < 0xC4000000 - 0x34 or not 0xC0000000 <= transport < 0xC4000000 - 0x30C:
        raise ValueError('native UI or transport is not ready')
    if word(outer + 0x24) or word(outer + 0x2C) != 1 or word(transport + 0x308):
        raise ValueError('STOP and main page without a modal are required between mode actions')


def measure(link, vsb, operation, emit, restored=None, span=None):
    if operation == 'table':
        if span is None or len(span) != 2:
            raise ValueError('an explicit SRAM table span is required')
        first, limit = span
        if not TABLE_START <= first < limit <= TABLE_END or first & (TABLE_BYTES-1) or limit-first != TABLE_BYTES:
            raise ValueError('an aligned 16 KiB SRAM table span is required')
    else:
        if span is not None:
            raise ValueError('only SRAM table capture accepts a span')
        first, limit = START, END
    preflight(link, vsb)
    quiescent(link)
    regions = ((STUB, 0x300), (RESULT, 32), (MAP, MAP_BYTES))
    backup = [(address, link.read(address, size)) for address, size in regions]
    confirmed = False
    step = MAP_BYTES * 4096 if operation == 'check' else MAP_BYTES if operation == 'table' else limit - first
    try:
        for start in range(first, limit, step):
            end = min(start + step, limit)
            confirmed = False
            words = invoke(link, operation, start, end, secrets.randbits(32) or 1)
            confirmed = True
            if words[2]:
                emit(dict(operation=operation, status=words[2], control=words[3],
                          refused=True, start=start, end=end))
                raise ValueError('cache/MMU or UI context refused; upper range was not touched')
            if operation == 'info':
                cache_type, dtcm, itcm = struct.unpack('<3I', link.read(MAP, 12))
                emit(dict(operation=operation, control=words[3], ttbr=words[4],
                          domain_control=words[5], fcse=words[6], cpu_id=words[7],
                          cache_type=cache_type, dtcm_region=dtcm, itcm_region=itcm))
                continue
            if operation == 'table':
                if words[4:6] != (start, end) or words[6] != end-start or words[7] != first:
                    raise ValueError('SRAM table completion differs from its source span')
                emit(dict(operation=operation, start=start, end=end, ttbr=words[7], control=words[3],
                          data=link.read(MAP, end-start)))
                continue
            if words[4:6] != (start, end) or words[7] != (end - start) // 4096:
                raise ValueError('completion range differs')
            row = dict(operation=operation, control=words[3], start=start, end=end)
            if operation == 'check':
                counts = link.read(MAP, (end - start) // 4096)
                changed = [[start + index * 4096, count] for index, count in enumerate(counts) if count]
                if len(changed) != words[6]:
                    raise ValueError('canary map and completion result differ')
                row['changed_blocks'] = changed
            emit(row)
    finally:
        if confirmed:
            for address, data in backup:
                quiescent(link)
                link.write_at(address, data)
            if restored:
                restored()


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--ram-overwrite-confirmed', action='store_true')
    parser.add_argument('--port-idle-confirmed', action='store_true')
    parser.add_argument('--stopped-main-confirmed', action='store_true')
    parser.add_argument('--operation', choices=('fill', 'check'))
    parser.add_argument('--vsb', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args(argv)
    if args.execute and not (args.ram_overwrite_confirmed and args.port_idle_confirmed and args.stopped_main_confirmed and args.operation and args.vsb and args.json):
        raise ValueError('execution needs fill/check, the own original, external report and all confirmations')
    return args


def main(argv=None):
    args = arguments(argv)
    if not args.execute:
        print(json.dumps(dict(hardware_contact=False, start=START, end=END,
                              excluded=['work buffer', 'start stack', 'IRQ and idle stack'],
                              baseline='fresh own original with only BLECH SysEx; no other extensions',
                              protocol='one fill, then mode actions only after exit; check again at STOP/main',
                              modes=['sampling mono/stereo', 'resampling mono/stereo', 'import', 'export', 'USB'],
                              limitation='canaries observe changes, not complete memory ownership',
                              next='obtain consent for a RAM fill between completed actions on a backed-up test card'), indent=2))
        return 0
    output = args.json.resolve()
    if any((part / '.git').exists() for part in (output, *output.parents)):
        raise ValueError('report must be outside a repository')
    vsb = args.vsb.read_bytes()
    rows = []
    report = dict(hardware_contact=False, flash_writes=False, card_writes=False, dsp_writes=False,
                  target_ram_restored=False, scratch_restored=False, reboot_required=True, observations=rows,
                  proves_complete_memory_ownership=False, error=None)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        def save():
            file.seek(0)
            file.truncate()
            json.dump(report, file, indent=2)
            file.flush()
        def emit(row):
            rows.append(row)
            save()
            print(json.dumps(row), flush=True)
        def restored():
            report['scratch_restored'] = True
            save()
        save()
        try:
            from blue_report import midi_ask, search
            report['hardware_contact'] = True
            ask, _ = midi_ask()
            device = search(ask)
            if device['model'] != 0x24 or device['version'] != '2.02':
                raise ValueError('red Sampler 2.02 required')
            measure(Link(ask, device['channel'], device['model']), vsb, args.operation, emit, restored)
        except BaseException as error:
            report['error'] = str(error)
        save()
    print(json.dumps(dict(complete=report['error'] is None, scratch_restored=report['scratch_restored'], report=str(output))))
    return 1 if report['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
