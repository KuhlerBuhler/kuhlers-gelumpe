"""Observe native voice flags through CRC-checked READ, without EXEC or writes.

Default is an offline plan. --observe requires the matching own red Sampler
VSB and a new report outside a repository. No notes or transport commands
are sent. Double reads detect changes during a snapshot, not ABA reuse.
"""
import argparse
import hashlib
import json
import struct
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'patch'))
from sample_swap_probe import enc, dec
import sample_swap as swap

FLAG_SIGN, FLAG_BITS = 0xC0691486, 0xC069143B
VOICES, STRIDE, COUNT = 0xC06916A0, 0x48, 24
FINGERPRINTS = ((0xC009115C, 0x34), (0xC00998B4, 0x90), (0xC0091F5C, 0xD0))


class ReadOnlyLink:
    def __init__(self, ask, channel, model):
        if model != 0x24:
            raise ValueError('only the red Sampler is mapped')
        self.ask, self.head, self.largest = ask, [0x42, 0x30 + channel, 0, 1, model], 1024

    def call(self, command, body, reply):
        if command not in (0x60, 0x61):
            raise ValueError('only INFO and READ are allowed')
        raw = self.ask([0xF0, *self.head, command, *enc(body), 0xF7])
        if raw[:7] != [0xF0, *self.head, reply] or raw[-1:] != [0xF7]:
            raise ValueError('unexpected BLECH reply; observation stopped')
        return dec(raw[7:-1])

    def info(self):
        raw = self.call(0x60, b'', 0x68)
        if len(raw) != 24:
            raise ValueError('unknown INFO layout')
        status, version, flags, largest, _, _ = struct.unpack('<6I', raw)
        if status or version != 1 or flags & 5 != 5 or not 1024 <= largest <= 32768:
            raise ValueError('BLECH v1 with CRC READ required')
        self.largest = largest

    def read(self, address, count):
        data = bytearray()
        while len(data) < count:
            at, size = address + len(data), min(self.largest, count - len(data))
            raw = self.call(0x61, struct.pack('<2I', at, size), 0x69)
            if len(raw) < 16:
                raise ValueError('truncated READ')
            status, got, length, crc = struct.unpack_from('<4I', raw)
            part = raw[16:]
            if status or (got, length) != (at, size) or len(part) != size or zlib.crc32(part) != crc:
                raise ValueError('READ status, address, size or CRC differs')
            data.extend(part)
        return bytes(data)


def source_fingerprints(vsb):
    if swap.sample_swap_io.validate_firmware(vsb) not in ('stock', 'hacktribe'):
        raise ValueError('only the mapped red Sampler builds are supported')
    spans = []
    for address, count in FINGERPRINTS:
        at = address - 0xC0000000 + 0x100
        data = vsb[at:at + count]
        if hashlib.sha256(data).hexdigest() != swap.CALLED_SHA[address]:
            raise ValueError('the own firmware does not contain the mapped voice layout')
        spans.append((address, data))
    return spans


def check_fingerprints(link, spans):
    for address, expected in spans:
        if link.read(address, len(expected)) != expected:
            raise ValueError('device voice code differs from the own firmware')


def snapshot(link):
    def read():
        sign = link.read(FLAG_SIGN, COUNT)
        flags = link.read(FLAG_BITS, COUNT)
        records = link.read(VOICES, STRIDE * COUNT)
        voices = []
        for index in range(COUNT):
            at = index * STRIDE
            voices.append(dict(index=index, busy=bool(sign[index] & 0x80 or flags[index] & 3),
                               sign=sign[index], flags=flags[index],
                               part=struct.unpack_from('<I', records, at + 4)[0],
                               slot=struct.unpack_from('<H', records, at + 0x3A)[0],
                               import_number=struct.unpack_from('<H', records, at + 0x40)[0]))
        return voices

    before, after = read(), read()
    return dict(stable=before == after, voices=after)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    parser.add_argument('--vsb', type=Path)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--hz', type=float, default=5)
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 300 or not 1 <= args.hz <= 10:
        raise ValueError('duration must be 1..300 seconds and rate 1..10 Hz')
    if args.observe and not (args.vsb and args.json):
        raise ValueError('--observe requires --vsb and --json')
    return args


def main(argv=None):
    args = arguments(argv)
    if not args.observe:
        print(json.dumps(dict(hardware_contact=False, mode='offline plan', operations=['SEARCH', 'INFO', 'READ'],
                              checks=['24 native voice flags', 'cached slot and import', 'double-read stability'],
                              limitation='sampled observations cannot prove the absence of ABA reuse'), indent=2))
        return 0
    report = args.json.resolve()
    if any((part / '.git').exists() for part in (report, *report.parents)):
        raise ValueError('the report belongs outside a repository')
    spans = source_fingerprints(args.vsb.read_bytes())
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open('x') as output:
        header = dict(mode='observe', writes=False, execute=False, audio_recorded=False,
                      atomic=False, aba_reuse='not detectable', requested_hz=args.hz,
                      operations=['SEARCH', 'INFO', 'READ'])
        output.write(json.dumps(header)[:-1] + ', "snapshots": [')
        count, stable, started, error = 0, 0, time.monotonic(), None
        attempted, identified = False, False
        try:
            from blue_report import midi_ask, search
            attempted = True
            ask, _ = midi_ask(None)
            device = search(ask)
            identified = True
            if device['model'] != 0x24 or device['version'] != '2.02':
                raise ValueError('red Sampler 2.02 required')
            link = ReadOnlyLink(ask, device['channel'], device['model'])
            link.info()
            check_fingerprints(link, spans)
            started = time.monotonic()
            while time.monotonic() - started < args.seconds:
                start = time.monotonic() - started
                row = snapshot(link)
                row.update(start_seconds=start, end_seconds=time.monotonic() - started)
                output.write((',' if count else '') + json.dumps(row))
                output.flush()
                count += 1
                stable += int(row['stable'])
                delay = min(args.seconds, start + 1 / args.hz) - (time.monotonic() - started)
                if delay > 0:
                    time.sleep(delay)
        except (Exception, KeyboardInterrupt, SystemExit) as caught:
            error = type(caught).__name__ + ': ' + str(caught)
        summary = dict(ok=error is None, hardware_contact_attempted=attempted,
                       hardware_identified=identified, samples=count, stable_samples=stable,
                       elapsed_seconds=time.monotonic() - started, error=error)
        output.write('], "result": ' + json.dumps(summary) + '}\n')
    print(json.dumps(dict(report=str(report), **summary), indent=2))
    return 0 if error is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
