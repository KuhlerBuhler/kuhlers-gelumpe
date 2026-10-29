"""Test slot transactions in a generated root-level card file, independently of installed swap code.

Default is a plan with no MIDI. --execute requires the own VSB and
--card-write-confirmed. Only an unused random BTxxxxxx.all and its journal
are touched. An unconfirmed EXEC stops without retry or RAM cleanup.
--preflight checks native code and idle state with INFO and READ only.
"""
import argparse
import hashlib
import json
import re
import secrets
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'patch'))
sys.path.insert(0, str(HERE.parent / 'emu'))
import arm
import sample_store
import sampleset
from sample_swap_paths import Link
from sample_swap_probe import MAGIC, STUB, elapsed

CODE, SCRATCH, SOURCE = 0xC3F00000, 0xC3E00000, 0xC3D00000
REGIONS = ((STUB, 1024), (CODE, 0xA000), (SCRATCH, 0x20000), (SOURCE, 0x20000))
READER, CONTEXT, PATH = SCRATCH + 0x1D000, SCRATCH + 0x1D010, SCRATCH + 0x1F000
FIL, GOT, BUFFER = SCRATCH + 0x1A000, SCRATCH + 0x1A240, SCRATCH + 0x3000
TIMER, HZ = 0x01F0D000, 150000000
TRANSPORT_GLOBAL = 0
SPANS = ((0xC009DB60, 0xB00, '1fee2e34672d676636cc44dfeaf6fffb0085766fe43b513f2250c023df11c2cf'),
         (0xC009E9B8, 0x148, 'c780e1a223851dc1480a08a7038091cfa03672277490b6167311edf40ad5c1c8'))


def test_path(path):
    return re.fullmatch(rb'SD:/BT[0-9A-F]{6}\.all', path) is not None


def idle(link):
    word = lambda at: struct.unpack('<I', link.read(at, 4))[0]
    if word(0xC0188530) not in (0, 0xFFFFFFFF):
        raise ValueError('active or faulted swap owns the test RAM')
    manager = word(0xC03404C0)
    if not 0xC0200000 <= manager < 0xC4000000 or word(manager + 0x2C) != 1 or word(manager + 0x24):
        raise ValueError('leave the device on its main screen without a window')
    transport = word(TRANSPORT_GLOBAL)
    if not 0xC0200000 <= transport < 0xC4000000:
        raise ValueError('invalid transport object')
    if word(transport + 0x308) or link.read(transport + 0x312, 1) != b'\0':
        raise ValueError('stop playback and leave sampling before this test')


def validate_device(link, vsb):
    global TRANSPORT_GLOBAL
    if len(vsb) != 0x200100:
        raise ValueError('own Sampler 2.02 VSB required')
    for at, count, expected in SPANS:
        own = vsb[at - 0xC0000000 + 0x100:at - 0xC0000000 + 0x100 + count]
        if hashlib.sha256(own).hexdigest() != expected or link.read(at, count) != own:
            raise ValueError(f'native file API differs at {at:#x}; nothing written')
    at = 0xC0030D28
    own = vsb[at - 0xC0000000 + 0x100:at - 0xC0000000 + 0x100 + 0x34]
    if struct.unpack_from('<I', own, 4)[0] != 0xE59F4024 or link.read(at, len(own)) != own:
        raise ValueError('transport getter differs; nothing written')
    TRANSPORT_GLOBAL = struct.unpack_from('<I', own, 0x30)[0]
    idle(link)


def program():
    body = sample_store.source(SCRATCH)
    thunks = []
    for i, (name, at) in enumerate(sample_store.API.items()):
        target = CODE + 0x8000 + i * 16
        body = body.replace(f'.equ STORE_FS_{name}, {at:#x}', f'.equ STORE_FS_{name}, {target:#x}')
        thunks.append(f'.org {target}\nldr r12, ={at}\nbx r12\n.pool\n')
    body += f'''
.org {CODE + 0x6000}
probe_source:
    push {{r4-r8, lr}}
    ldr r4, [r0]
    ldr r5, [r0, #4]
    cmp r1, r5
    bhi probe_source_bad
    sub r5, r5, r1
    cmp r3, r5
    bhi probe_source_bad
    add r4, r4, r1
    mov r5, r3
    cmp r3, #0
    beq probe_source_ok
probe_source_byte:
    ldrb r0, [r4], #1
    strb r0, [r2], #1
    subs r3, r3, #1
    bne probe_source_byte
probe_source_ok:
    mov r0, #0
    mov r1, r5
    pop {{r4-r8, pc}}
probe_source_bad:
    mov r0, #1
    mov r1, #0
    pop {{r4-r8, pc}}
probe_exists:
    push {{r4-r8, lr}}
    mov r1, r0
    ldr r0, ={FIL}
    mov r2, #1
    bl STORE_FS_OPEN
    cmp r0, #0
    movne r1, #0
    popne {{r4-r8, pc}}
    ldr r0, ={FIL}
    ldr r4, [r0, #12]
    bl STORE_FS_CLOSE
    cmp r0, #0
    movne r0, #1
    mov r1, r4
    pop {{r4-r8, pc}}
probe_read:
    push {{r4-r8, lr}}
    mov r1, r0
    ldr r0, ={FIL}
    mov r2, #1
    bl STORE_FS_OPEN
    cmp r0, #0
    movne r1, #0
    popne {{r4-r8, pc}}
    ldr r0, ={FIL}
    ldr r4, [r0, #12]
    cmp r4, #65536
    bhi probe_read_large
    ldr r1, ={BUFFER}
    mov r2, r4
    ldr r3, ={GOT}
    bl STORE_FS_READ
    mov r5, r0
    ldr r0, ={GOT}
    ldr r0, [r0]
    cmp r0, r4
    movne r5, #1
    b probe_read_close
probe_read_large:
    mov r5, #3
probe_read_close:
    ldr r0, ={FIL}
    bl STORE_FS_CLOSE
    orr r0, r0, r5
    mov r1, r4
    pop {{r4-r8, pc}}
probe_remove:
    b STORE_FS_UNLINK
.pool
'''
    built = arm.assemble(body + '\n' + ''.join(thunks), origin=CODE)
    spans = sorted((at, at + len(data)) for at, data in built.sections)
    if any(lo < CODE or hi > CODE + 0xA000 for lo, hi in spans):
        raise ValueError('probe code exceeds its owned RAM')
    if any(spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1)):
        raise ValueError('probe code sections overlap')
    return built.sections, built.symbols


def stub(function, args, token):
    words = ', '.join(map(str, (MAGIC, token, 0, 0xFFFFFFFF, *([0] * 8))))
    load = '\n'.join(f'ldr r{i}, ={value}' for i, value in enumerate(args))
    code = f'''
    b start
result:
    .word {words}
start:
    push {{r4-r11, r12, lr}}
    ldr r4, =result
    ldr r1, [r4, #4]
    cmp r0, r1
    bne finished
    mov r0, #1
    str r0, [r4, #8]
    ldr r11, ={TIMER}
    ldr r0, [r11, #0x18]
    str r0, [r4, #32]
    ldr r0, [r11, #0x20]
    str r0, [r4, #36]
    ldr r0, [r11, #0x24]
    str r0, [r4, #40]
    ldr r0, [r11, #0x10]
    str r0, [r4, #24]
    {load}
    ldr r12, ={function}
    blx r12
    str r0, [r4, #12]
    str r1, [r4, #16]
    str r2, [r4, #20]
    ldr r0, [r11, #0x10]
    str r0, [r4, #28]
    mov r0, #2
    str r0, [r4, #8]
finished:
    ldr r0, ={MAGIC}
    pop {{r4-r11, r12, pc}}
.pool
'''
    data = arm.assemble(code, origin=STUB).bytes
    if len(data) > 1024:
        raise ValueError('probe stub exceeds its region')
    return data


class CheckedLink:
    def __init__(self, link):
        self.link = link
        self.failed = False

    def call(self, name, *args):
        try:
            return getattr(self.link, name)(*args)
        except BaseException:
            self.failed = True
            raise

    def read(self, *args):
        return self.call('read', *args)

    def write_at(self, *args):
        return self.call('write_at', *args)

    def execute(self, *args):
        return self.call('execute', *args)


def run(link, path, backup=None):
    if not test_path(path):
        raise ValueError('only a generated BTxxxxxx.all at the card root is allowed')
    link = CheckedLink(link)
    report = dict(ok=False, path=path.decode(), ram_restored=False, execution_unconfirmed=False,
                  communication_unconfirmed=False, operations=[])
    saved = []
    uncertain = False
    modified = False
    try:
        idle(link)
        for at, count in REGIONS:
            data = link.read(at, count)
            if len(data) != count:
                raise ValueError('RAM backup incomplete')
            saved.append((at, data))
            if backup and backup(at, data) != len(data):
                raise ValueError('host RAM backup incomplete; nothing written')
        sections, symbols = program()
        for at, data in sections:
            modified = True
            link.write_at(at, data)
        def call(name, *args):
            nonlocal uncertain
            idle(link)
            token = secrets.randbits(31) | 1
            link.write_at(STUB, stub(symbols[name], args, token))
            started = time.monotonic()
            try:
                link.execute(token)
                words = struct.unpack('<12I', link.read(STUB + 4, 48))
                if words[:3] != (MAGIC, token, 2):
                    raise ValueError('completion marker differs')
            except BaseException:
                uncertain = True
                raise
            wall = time.monotonic() - started
            ticks = elapsed(words[6], words[7], words[8])
            valid = bool(ticks) and wall < 1 and words[8] >= HZ - 1 and words[9] & 0xC0 == 0x80 and words[10] & 1
            report['operations'].append(dict(operation=name, status=words[3], milliseconds=ticks / HZ * 1000 if valid else None))
            return words[3], words[4]
        def select_path(name):
            link.write_at(PATH, name + b'\0')
        select_path(path)
        if call('probe_exists', PATH)[0] not in (4, 5):
            raise ValueError('test file already exists or card lookup failed')
        select_path(path[:-3] + b'txn')
        if call('probe_exists', PATH)[0] not in (4, 5):
            raise ValueError('journal already exists or card lookup failed')
        select_path(path)
        expected = bytes(sampleset.build({}))
        for slot, name, frames in ((500, 'Own first', 512), (501, 'Own other', 512), (500, 'Own replacement', 1024)):
            wave = sampleset.wav(slot, name, frames)
            if len(wave) > REGIONS[3][1]:
                raise ValueError('generated sample exceeds its owned RAM')
            link.write_at(SOURCE, wave)
            link.write_at(CONTEXT, struct.pack('<II', SOURCE, len(wave)))
            link.write_at(READER, struct.pack('<II', symbols['probe_source'], CONTEXT))
            status, _ = call('store_put', PATH, READER, slot, len(wave))
            if status:
                raise ValueError(f'store_put returned {status}; test file retained')
            before = len(expected)
            expected = bytearray(expected + wave)
            struct.pack_into('<I', expected, 16 + slot * 4, before)
            status, size = call('probe_read', PATH)
            if status or size != len(expected) or link.read(BUFFER, size) != expected:
                raise ValueError('stored file differs; test file retained')
        if call('store_delete', PATH, 501)[0]:
            raise ValueError('store_delete refused; test file retained')
        struct.pack_into('<I', expected, 16 + 501 * 4, 0)
        status, size = call('probe_read', PATH)
        if status or size != len(expected) or link.read(BUFFER, size) != expected:
            raise ValueError('deleted index or unchanged payload differs')
        select_path(path[:-3] + b'txn')
        if call('probe_exists', PATH)[0] not in (4, 5):
            raise ValueError('unexpected journal remains; test files retained')
        select_path(path)
        if call('probe_remove', PATH)[0]:
            raise ValueError('test file removal failed')
        if call('probe_exists', PATH)[0] not in (4, 5):
            raise ValueError('test file still exists')
        report['ok'] = True
    except BaseException as error:
        report['error'] = str(error)
        report['execution_unconfirmed'] = uncertain
        report['communication_unconfirmed'] = link.failed or uncertain
    finally:
        if modified and not uncertain and not link.failed:
            try:
                idle(link)
                for at, data in reversed(saved):
                    link.write_at(at, data)
                    if link.read(at, len(data)) != data:
                        raise ValueError('RAM restoration differs')
                report['ram_restored'] = True
            except BaseException as error:
                report['ok'] = False
                report['restore_error'] = str(error)
                report['communication_unconfirmed'] = link.failed
    return report


def arguments(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--preflight', action='store_true')
    p.add_argument('--card-write-confirmed', action='store_true')
    p.add_argument('--vsb', type=Path)
    p.add_argument('--json', type=Path)
    p.add_argument('--backup-dir', type=Path)
    a = p.parse_args(argv)
    if a.execute and not (a.card_write_confirmed and a.vsb and a.json and a.backup_dir):
        raise ValueError('--execute requires --card-write-confirmed, --vsb, --json and --backup-dir')
    if a.preflight and not a.vsb:
        raise ValueError('--preflight requires --vsb')
    return a


def outside_repo(path):
    if any((part / '.git').exists() for part in (path.resolve(), *path.resolve().parents)):
        raise ValueError('reports and RAM backups belong outside a repository')


def main(argv=None):
    a = arguments(argv)
    if not a.execute and not a.preflight:
        print(json.dumps(dict(mode='offline plan', hardware_contact=False, card='generated BTxxxxxx.all at the root',
                              checks=['put two slots', 'replace one slot', 'delete one index', 'readback', 'remove own file', 'restore RAM']), indent=2))
        return 0
    if a.json:
        outside_repo(a.json)
    if a.backup_dir:
        outside_repo(a.backup_dir)
    if a.execute and a.backup_dir.exists():
        raise ValueError('use a new backup directory')
    from blue_report import midi_ask, search
    ask, _ = midi_ask(None)
    device = search(ask)
    if device['model'] != 0x24 or device['version'] != '2.02':
        raise ValueError('red Sampler 2.02 required')
    link = Link(ask, device['channel'], device['model'])
    link.info()
    validate_device(link, a.vsb.read_bytes())
    if a.preflight:
        report = dict(hardware_contact=True, korg_version=device['version'], native_api_match=True,
                      idle=True, operations=['SEARCH', 'INFO', 'READ'], writes=False)
        if a.json:
            a.json.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 0
    a.backup_dir.mkdir(parents=True)
    path = f'SD:/BT{secrets.token_hex(3).upper()}.all'.encode()
    a.json.parent.mkdir(parents=True, exist_ok=True)
    a.json.write_text(json.dumps(dict(hardware_contact=True, phase='preparing', path=path.decode(),
                                     ram_restored=False, operations=[]), indent=2) + '\n')
    def backup(at, data):
        saved = a.backup_dir / f'{at:08x}.bin'
        count = saved.write_bytes(data)
        if saved.read_bytes() != data:
            raise ValueError('host RAM backup readback differs')
        return count
    report = run(link, path, backup)
    report.update(hardware_contact=True, korg_version=device['version'])
    a.json.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] and report['ram_restored'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
