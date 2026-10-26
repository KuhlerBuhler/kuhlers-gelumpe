"""Profile a copy of the Hacktribe 2.02 sample loader through BLECH EXEC.

Uses the 1 KiB upload buffer and a block owned through the firmware allocator.
The card is opened read-only by the loader; firmware code and flash stay intact.
Requires the owner's original and running firmware, stopped transport and
--execute. An EXEC timeout stops without further writes or an automatic retry.
"""
import argparse
import hashlib
import json
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'patch'))
import arm
import sample_seek

IMAGE, HEADER = 0xC0000000, 0x100
STUB, COPY, RESULT = 0xC1000000, 0xC1004000, 0xC1003000
START, END = 0xC0035B10, 0xC0036790
CODE = [(START, 0xC0036400), (0xC00364F0, 0xC0036770)]
TIMER, TICK, TRANSPORT = 0x01F0D000, 0xC06A292C, 0xC06BC318
HERTZ, MAGIC = 150_000_000, 0x50524F46
FUNCTIONS = [('read', 0xC009DD74), ('seek', 0xC009E404),
             ('parser', START), ('slot', 0xC004EDF0), ('dsp', 0xC004EF28)]
EXTRA = [('read_pcm', 0xC009DD74), ('seek_scan', 0xC009E404),
         ('seek_fmt', 0xC009E404), ('seek_meta', 0xC009E404),
         ('seek_data', 0xC009E404), ('seek_end', 0xC009E404), ('seek_slot', 0xC009E404)]
SITES = {'read_pcm': [0xC00362FC, 0xC003635C], 'seek_scan': [0xC0035C94, 0xC0035D68],
         'seek_fmt': [0xC0035C74], 'seek_meta': [0xC0035DCC], 'seek_data': [0xC0035DFC],
         'seek_end': [0xC00363C0], 'seek_slot': [0xC00366E0]}
ALLOWED_DIFFERENCES = {0xC0035FB4, 0xC0035FC4, 0xC0035FD4,
                       0xC00364F0, 0xC00366D4, 0xC0036700, 0xC0036714}
SPANS = [(START, END - START), (0xC004EDF0, 0x1A4),
         (0xC009DB60, 0x10F4), (0xC00369F0, 0x30), (0xC0008F30, 0x40),
         (0xC0028DCC, 16), (0xC004EDDC, 20)]


def branch(address, target, link=False, condition=14):
    offset = target - address - 8
    if offset % 4 or not -(1 << 25) <= offset < (1 << 25):
        raise ValueError('ARM branch outside signed 24-bit range')
    return struct.pack('<I', condition << 28 | (0xB if link else 0xA) << 24 | (offset >> 2 & 0xFFFFFF))


def destination(address, word):
    offset = word & 0xFFFFFF
    if offset & 0x800000:
        offset -= 1 << 24
    return address + 8 + offset * 4


def relocate(data, old, new, code, wrappers):
    out = bytearray(data)
    for first, last in code:
        for address in range(first, last, 4):
            offset = address - old
            word = struct.unpack_from('<I', data, offset)[0]
            if word >> 25 & 7 != 5:
                continue
            target = destination(address, word)
            if target in wrappers and word & 0x1000000:
                target = wrappers[target]
            elif old <= target < old + len(data):
                target += new - old
            out[offset:offset + 4] = branch(address + new - old, target, bool(word & 0x1000000), word >> 28)
    return bytes(out)


def payload(path):
    data = Path(path).read_bytes()
    if len(data) != 0x200100:
        raise ValueError('expected a 2 MiB Sampler VSB with 256-byte header')
    return data[HEADER:]


def build(original, instrument=True, base=STUB, seek_anchor=False, dsp_checksum=False):
    STUB, COPY, RESULT = base, base + 0x4000, base + 0x3000
    raw = original[START - IMAGE:END - IMAGE]
    wrappers = {target: STUB + 0x800 + index * 0x100 for index, (_, target) in enumerate(FUNCTIONS)}
    wrapper_source = []
    counters = FUNCTIONS + [('convert24', STUB + 0x2000)] + EXTRA
    for index, (name, target) in enumerate(counters):
        address = STUB + 0x800 + index * 0x100
        callee = COPY if name == 'parser' else wrappers[target] if (name, target) in EXTRA else target
        amount = 'mov r8, r3' if name.startswith('read') else 'mov r8, r2' if name == 'dsp' else 'mov r8, r9' if name == 'convert24' else 'mov r8, #0'
        quantity = 'ldr r8, [r8]' if name.startswith('read') else 'mov r8, r8, lsl #1' if name in ('dsp', 'convert24') else ''
        wrapper_source.append(f'''
.org {address}
    push {{r4-r8, lr}}
    sub sp, sp, #8
    {amount}
    ldr r4, ={TICK}
    ldr r4, [r4]
    str r4, [sp]
    ldr r4, ={RESULT + 0x40 + index * 16}
    ldr r5, ={TIMER}
    ldr r5, [r5, #0x10]
    bl {callee}
    ldr r6, ={TIMER}
    ldr r7, [r6, #0x18]
    ldr r6, [r6, #0x10]
    subs r6, r6, r5
    addlo r6, r6, r7
    addlo r6, r6, #1
    ldr r12, ={TICK}
    ldr r12, [r12]
    ldr r7, [sp]
    sub r12, r12, r7
    ldr r7, [r4, #12]
    cmp r12, r7
    strhi r12, [r4, #12]
    ldr r7, [r4]
    add r7, r7, #1
    str r7, [r4]
    ldr r7, [r4, #4]
    add r7, r7, r6
    str r7, [r4, #4]
    {quantity}
    ldr r7, [r4, #8]
    add r7, r7, r8
    str r7, [r4, #8]
    add sp, sp, #8
    pop {{r4-r8, pc}}
.pool
''')
    clone = bytearray(relocate(raw, START, COPY, CODE, wrappers if instrument else {}))
    if instrument:
        for index, (name, _) in enumerate(counters):
            for site in SITES.get(name, []):
                offset = site - START
                clone[offset:offset + 4] = branch(COPY + offset, STUB + 0x800 + index * 0x100, link=True)
        offset = 0xC0036368 - START
        clone[offset:offset + 4] = branch(COPY + offset, STUB + 0xD00, link=True)
        clone[offset + 4:offset + 8] = branch(COPY + offset + 4, COPY + 0xC0036310 - START)
    anchors = ''
    if seek_anchor:
        clone[:4] = branch(COPY, STUB + 0x2100)
        anchors = f'.org {STUB + 0x2100}\n' + sample_seek.parser_source(COPY + 4, 'profile_anchor')
        for index, (name, target) in enumerate(EXTRA):
            if not name.startswith('seek_') or name == 'seek_slot':
                continue
            address = STUB + 0x2200 + index * 0x100
            callee = STUB + 0x800 + (6 + index) * 0x100 if instrument else target
            anchors += f'.org {address}\n' + sample_seek.seek_source(callee, 'profile_' + name)
            for site in SITES[name]:
                clone[site - START:site - START + 4] = branch(COPY + site - START, address, link=True)
    crc_table = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
        crc_table.append(str(value))
    checksum_call = f'bl {STUB + 0x2800}\nstr r0, [r4, #36]' if dsp_checksum else ''
    source = f'''
.org {STUB}
    push {{r4-r8, lr}}
    ldr r4, ={RESULT}
    ldr r5, ={TIMER}
    ldr r0, [r5, #0x18]
    str r0, [r4, #12]
    ldr r0, [r5, #0x20]
    str r0, [r4, #16]
    ldr r0, [r5, #0x24]
    str r0, [r4, #20]
    ldr r0, ={TICK}
    ldr r0, [r0]
    str r0, [r4]
    ldr r0, =path
    bl {COPY + 0xC00364F0 - START}
    str r0, [r4, #8]
    ldr r0, ={TICK}
    ldr r0, [r0]
    str r0, [r4, #4]
    ldr r0, =0x01C40004
    ldr r0, [r0]
    str r0, [r4, #24]
    ldr r0, =0xC00F9C80
    ldr r0, [r0]
    str r0, [r4, #28]
    {checksum_call}
    ldr r0, ={MAGIC}
    str r0, [r4, #32]
    pop {{r4-r8, pc}}
.pool
path:
    .asciz "SD:KORG/blechtribe/Sample/e2sSample.all"
{''.join(wrapper_source) if instrument else ''}
.org {STUB + 0x2000}
    mov r3, r7
conversion_loop:
    cmp r0, r9
    bxge lr
    ldrb r1, [r3, #2]
    ldrb r2, [r3, #1]
    mov r1, r1, lsl #16
    add r1, r1, r2, lsl #8
    mov r1, r1, lsr #8
    mov r2, r0, lsl #1
    .word 0xE18710B2
    add r0, r0, #1
    add r3, r3, #3
    b conversion_loop
{anchors}
.org {STUB + 0x2800}
    push {{r4-r11, r12, lr}}
    ldr r4, =0x365EC0
    sub r5, r0, r4
    mvn r6, #0
    ldr r7, ={STUB + 0x2C00}
    ldr r8, ={STUB + 0x1800}
crc_block:
    cmp r5, #0
    beq crc_done
    cmp r5, #1024
    movlo r9, r5
    movhs r9, #1024
    mov r0, r8
    mov r1, r4
    mov r2, r9, lsr #1
    bl 0xC004EDDC
    mov r0, r8
    mov r1, r9
crc_byte:
    ldrb r2, [r0], #1
    eor r2, r6, r2
    and r2, r2, #255
    ldr r2, [r7, r2, lsl #2]
    eor r6, r2, r6, lsr #8
    subs r1, r1, #1
    bne crc_byte
    add r4, r4, r9
    sub r5, r5, r9
    b crc_block
crc_done:
    mvn r0, r6
    pop {{r4-r11, r12, pc}}
.pool
.org {STUB + 0x2C00}
    .word {','.join(crc_table)}
'''
    assembled = arm.assemble(source, STUB)
    out = bytearray(COPY - STUB + len(clone))
    for at, data in assembled.sections:
        out[at - STUB:at - STUB + len(data)] = data
    out[COPY - STUB:] = clone
    return bytes(out)


class Link:
    def __init__(self):
        import mido
        self.idle = True
        self.mido = mido
        names = [n for n in mido.get_input_names() if 'electribe' in n.lower() and 'SOUND' in n]
        if len(names) != 1 or names[0] not in mido.get_output_names():
            raise ValueError(f'expected one Electribe SOUND port, got {names}')
        self.inp, self.out = mido.open_input(names[0]), mido.open_output(names[0])
        found = self.ask([0xF0, 0x42, 0x50, 0, 0, 0xF7])
        if found[:4] != [0xF0, 0x42, 0x50, 1] or found[6] != 0x24:
            raise ValueError('expected red Sampler')
        self.head = [0x42, 0x30 + (found[4] & 15), 0, 1, found[6]]
        raw = self.call(0x60, b'', 0x68)
        status, version, flags, self.largest, _, _ = struct.unpack('<6I', raw)
        if status or version != 1 or flags & 0x47 != 0x47:
            raise ValueError('BLECH v1 read/write/EXEC required')

    def ask(self, message, timeout=6):
        for _ in self.inp.iter_pending():
            pass
        self.out.send(self.mido.Message('sysex', data=message[1:-1]))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for incoming in self.inp.iter_pending():
                if incoming.type == 'sysex':
                    return [0xF0, *incoming.data, 0xF7]
            time.sleep(0.005)
        raise TimeoutError('no answer; no retry or further writes')

    def call(self, command, body, reply, timeout=6):
        from flash_dump import enc, dec
        raw = self.ask([0xF0, *self.head, command, *enc(body), 0xF7], timeout)
        if raw[:7] != [0xF0, *self.head, reply] or raw[-1] != 0xF7:
            raise ValueError('unexpected BLECH reply')
        return dec(raw[7:-1])

    def read(self, address, length):
        if length > self.largest:
            return b''.join(self.read(address + at, min(self.largest, length - at)) for at in range(0, length, self.largest))
        raw = self.call(0x61, struct.pack('<II', address, length), 0x69)
        status, addr, count, crc = struct.unpack_from('<4I', raw)
        data = raw[16:]
        if status or (addr, count) != (address, length) or len(data) != length or zlib.crc32(data) != crc:
            raise ValueError('READ status, range or CRC mismatch')
        return data

    def write(self, data):
        if len(data) > 1024:
            raise ValueError('only the 1 KiB EXEC buffer may be uploaded')
        for offset in range(0, len(data), 1024):
            piece = data[offset:offset + 1024]
            address, crc = STUB + offset, zlib.crc32(piece)
            if self.call(0x62, struct.pack('<3I', address, len(piece), crc), 0x6A) != struct.pack('<3I', 0, address, len(piece)):
                raise ValueError('WRITE BEGIN refused')
            raw = self.call(0x63, piece, 0x6B)
            status, addr, count, got_crc = struct.unpack('<4I', raw)
            if status or (addr, count, got_crc) != (address, len(piece), crc):
                raise ValueError('WRITE DATA status, range or CRC mismatch')
        if self.read(STUB, len(data)) != data:
            raise ValueError('upload readback differs')

    def execute(self, source):
        self.write(arm.assemble(source, STUB).bytes)
        self.idle = False
        raw = self.call(0x6F, struct.pack('<II', STUB, 0), 0x70, timeout=45)
        status, address, value = struct.unpack('<3I', raw)
        if address != STUB:
            raise ValueError('unexpected EXEC address')
        self.idle = True
        if status:
            raise ValueError('EXEC refused')
        return value

    def upload(self, address, data):
        for offset in range(0, len(data), 768):
            piece = data[offset:offset + 768]
            source = f'''
    push {{r4, lr}}
    ldr r0, ={address + offset}
    ldr r1, =data
    ldr r2, ={len(piece)}
copy_loop:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne copy_loop
    ldr r0, ={MAGIC}
    pop {{r4, pc}}
.pool
data:
    .byte {','.join(str(n) for n in piece)}
'''
            if self.execute(source) != MAGIC:
                raise ValueError('RAM copy did not confirm return')
        if self.read(address, len(data)) != data:
            raise ValueError('allocated code readback differs')


def measure(link, original, instrument, seek_anchor, dsp_checksum):
    size = len(build(original, instrument, seek_anchor=seek_anchor, dsp_checksum=dsp_checksum))
    backup, owned, cleanup = link.read(STUB, 1024), None, True
    try:
        address = link.execute(f'push {{r4, lr}}\nldr r0, ={size}\nbl 0xC0028DD0\npop {{r4, pc}}')
        if not 0xC06A2940 <= address < address + size <= 0xC08A2940 or address % 4:
            raise ValueError('allocator did not return a valid owned heap block')
        owned = address
        image = build(original, instrument, base=address, seek_anchor=seek_anchor, dsp_checksum=dsp_checksum)
        link.upload(address, image)
        if struct.unpack('<I', link.read(TRANSPORT, 4))[0]:
            raise ValueError('transport started before measurement')
        value = link.execute(f'push {{r4, lr}}\nldr r4, ={address}\nblx r4\npop {{r4, pc}}')
        if value != MAGIC:
            raise ValueError('EXEC return mismatch')
        length = 64 + 16 * (len(FUNCTIONS) + 1 + len(EXTRA))
        words = struct.unpack(f'<{length // 4}I', link.read(address + 0x3000, length))
        if words[8] != MAGIC:
            raise ValueError('missing completion marker')
        return words, address, size
    except (TimeoutError, KeyboardInterrupt):
        cleanup = False
        raise
    finally:
        if cleanup and link.idle:
            if owned is not None:
                link.execute(f'push {{r4, lr}}\nldr r0, ={owned}\nbl 0xC0028DD8\npop {{r4, pc}}')
            link.write(backup)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--original', required=True)
    parser.add_argument('--running-vsb', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--seek-anchor', action='store_true')
    parser.add_argument('--dsp-checksum', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    original, running = payload(args.original), payload(args.running_vsb)
    for address in range(START, END, 4):
        offset = address - IMAGE
        if address not in ALLOWED_DIFFERENCES and original[offset:offset + 4] != running[offset:offset + 4]:
            raise ValueError(f'unexpected loader change at {address:#x}')
    image = build(original, not args.baseline, seek_anchor=args.seek_anchor, dsp_checksum=args.dsp_checksum)
    if not args.execute:
        print(json.dumps({'allocated_bytes': len(image), 'instrumented': not args.baseline,
                          'writes': '1 KiB EXEC buffer and owned heap block'}))
        return
    link = Link()
    if struct.unpack('<I', link.read(TRANSPORT, 4))[0]:
        raise ValueError('transport is running')
    for address, length in SPANS:
        if link.read(address, length) != running[address - IMAGE:address - IMAGE + length]:
            raise ValueError(f'running firmware differs at {address:#x}')
    counter_specs = FUNCTIONS + [('convert24', 0)] + EXTRA
    words, address, size = measure(link, original, not args.baseline, args.seek_anchor, args.dsp_checksum)
    counters = {}
    for index, (name, _) in enumerate(counter_specs):
        count, ticks, amount, maximum_ms = words[16 + index * 4:20 + index * 4]
        if maximum_ms >= 1000:
            raise ValueError(f'{name}: span crossed multiple possible timer periods')
        counters[name] = {'count': count, 'ticks': ticks, 'ms': ticks / (HERTZ / 1000), 'bytes': amount, 'maximum_span_ms': maximum_ms}
    result = {'instrumented': not args.baseline, 'seek_anchor': args.seek_anchor, 'loader_ms': (words[1] - words[0]) & 0xFFFFFFFF,
              'result': words[2], 'timer_period': words[3], 'timer_tcr': words[4], 'timer_tgcr': words[5],
              'mmcclk': hex(words[6]), 'dsp_cursor': hex(words[7]), 'counters': counters,
              'original_sha256': hashlib.sha256(original).hexdigest(),
              'running_sha256': hashlib.sha256(running).hexdigest(), 'upload_restored': True,
              'allocated_address': hex(address), 'allocated_bytes': size, 'allocation_freed': True}
    if args.dsp_checksum:
        result['dsp_crc32'] = f'{words[9]:08x}'
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
