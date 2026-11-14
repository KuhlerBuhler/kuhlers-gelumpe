# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, process-isolated access to the GNU Blackfin simulator worker."""
import os
import math
from pathlib import Path
import selectors
import struct
import subprocess
import tempfile
import time

LIMIT = 1 << 20
REGISTER_NAMES = ([f'R{i}' for i in range(8)] + [f'P{i}' for i in range(6)] + ['SP', 'FP']
                  + [f'{kind}{i}' for kind in ('I', 'M', 'B', 'L') for i in range(4)]
                  + ['A0.X', 'A0.W', 'A1.X', 'A1.W', 'ASTAT', 'RETS', 'LC0', 'LT0', 'LB0',
                     'LC1', 'LT1', 'LB1', 'CYCLES', 'CYCLES2', 'USP', 'SEQSTAT', 'SYSCFG',
                     'RETI', 'RETX', 'RETN', 'RETE', 'PC'])


class BackendError(RuntimeError):
    pass


class _ROMCall(Exception):
    def __init__(self, data):
        self.steps, self.caller, *values = struct.unpack('<56I', data)
        self.registers = dict(zip(REGISTER_NAMES, values))

    def __str__(self):
        values = ' '.join(f'{name}=0x{value:08x}' for name, value in self.registers.items())
        return (f'unsupported Blackfin on-chip ROM call; no ROM code is executed: '
                f'caller=0x{self.caller:08x} {values}')


class BlackfinBackend:
    def __init__(self, worker, *, timeout=5, operating=False, rom=None):
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('a finite positive Blackfin deadline is required')
        self.process = None
        self.timeout = timeout
        self.rom = rom
        self._stderr = tempfile.TemporaryFile()
        self._selector = selectors.DefaultSelector()
        self._deadline = time.monotonic() + timeout
        try:
            path = Path(worker).resolve(strict=True)
            self.process = subprocess.Popen([str(path)] + (['--operating'] if operating else []), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=self._stderr, bufsize=0)
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
            self._selector.register(self.process.stdout, selectors.EVENT_READ)
            if self._response() != b'BFIN4':
                raise BackendError('invalid Blackfin worker handshake; rebuild the SDK for BFIN4')
        except (OSError, BackendError) as error:
            detail = self._diagnostic()
            self.close()
            raise BackendError(f'Blackfin worker: {error}{detail}') from error

    def _diagnostic(self):
        if self._stderr.closed:
            return ''
        self._stderr.seek(0, os.SEEK_END)
        self._stderr.seek(max(0, self._stderr.tell() - 2048))
        data = self._stderr.read().decode('utf8', errors='replace').strip()
        return f': {data}' if data else ''

    def _send(self, data):
        view = memoryview(data)
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdin, selectors.EVENT_WRITE)
            while view:
                remaining = self._deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise BackendError('Blackfin worker deadline exceeded while writing')
                try:
                    count = os.write(self.process.stdin.fileno(), view)
                except BlockingIOError:
                    continue
                if count <= 0:
                    raise BackendError('Blackfin worker stopped accepting requests')
                view = view[count:]

    def _receive(self, size):
        data = bytearray()
        while len(data) < size:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0 or not self._selector.select(remaining):
                raise BackendError('Blackfin worker deadline exceeded')
            try:
                chunk = os.read(self.process.stdout.fileno(), size - len(data))
            except BlockingIOError:
                continue
            if not chunk:
                raise BackendError('Blackfin worker exited before answering')
            data.extend(chunk)
        return bytes(data)

    def _response(self, *, rom=False):
        status, count = struct.unpack('<II', self._receive(8))
        if status == 3:
            if not rom or count != 4 * 56:
                raise BackendError('invalid Blackfin ROM diagnostic')
            raise _ROMCall(self._receive(count))
        if status or count > LIMIT:
            raise BackendError(f'Blackfin worker failed with status {status}')
        return self._receive(count)

    def _request(self, op, address, count, data=b'', extra=0):
        if self.process is None:
            raise BackendError('Blackfin worker is closed')
        self._deadline = time.monotonic() + self.timeout
        try:
            self._send(struct.pack('<III', op, address, count) + data)
            response = self._response(rom=op == 5)
            return self._receive(extra) if extra else response
        except (OSError, BackendError) as error:
            detail = self._diagnostic()
            self.close()
            raise BackendError(f'{error}{detail}') from error

    @staticmethod
    def _span(address, size):
        if not isinstance(address, int) or not isinstance(size, int) or not 0 <= size <= LIMIT or not 0 <= address <= 0xFFFFFFFF or address + size > 1 << 32:
            raise ValueError('invalid bounded Blackfin memory span')

    def read(self, address, size):
        self._span(address, size)
        return self._request(1, address, size)

    def write(self, address, data):
        data = bytes(data)
        self._span(address, len(data))
        self._request(2, address, len(data), data)

    def register(self, number):
        if not 0 <= number <= 53:
            raise ValueError('invalid Blackfin register')
        return struct.unpack('<I', self._request(3, number, 0, extra=4))[0]

    def set_register(self, number, value):
        if not 0 <= number <= 53 or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError('invalid Blackfin register/value')
        self._request(4, number, value)

    def host_event(self, event):
        if not isinstance(event, int) or not 0 <= event <= 0xFFFFFFFF:
            raise ValueError('invalid HOSTDP event')
        self._request(6, event, 0)

    def run(self, steps, *, until=0xFFFFFFFF):
        if not 1 <= steps <= 1000000 or not 0 <= until <= 0xFFFFFFFF:
            raise ValueError('invalid Blackfin execution budget')
        count, calls, pc = 0, 0, 0
        while count < steps:
            try:
                executed, pc = struct.unpack('<II', self._request(5, steps-count, until, extra=8))
                count += executed
                break
            except _ROMCall as error:
                count += error.steps
                try:
                    if self.rom is None:
                        raise BackendError('no ROM model selected')
                    if calls >= 64:
                        raise BackendError('Blackfin ROM service budget exceeded')
                    self.rom.handle(self, error.registers)
                    calls += 1
                    pc = self.register(53)
                except (BackendError, ValueError) as failure:
                    self.close()
                    raise BackendError(f'{failure}: {error}') from failure
        return dict(steps=count, pc=pc, reached=pc == until)

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdin.close()
            process.stdout.close()
        self._selector.close()
        self._stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def boot_blocks(data):
    """Validated ADI headers; INIT is the boot-ROM stage replaced by direct loading."""
    data = bytes(data)
    offset, blocks, final = 0, [], False
    while offset < len(data):
        if len(blocks) >= 4096 or offset + 16 > len(data):
            raise BackendError('truncated or oversized Blackfin boot stream')
        header = data[offset:offset+16]
        code, target, size, argument = struct.unpack('<IIII', header)
        checksum = 0
        for value in header:
            checksum ^= value
        if checksum or code >> 24 != 0xAD or target + size > 1 << 32 or size > 64 << 20:
            raise BackendError('invalid Blackfin boot header')
        flags = code & 65535
        count = 0 if flags & 0x100 else size
        offset += 16
        if offset + count > len(data):
            raise BackendError('truncated Blackfin boot payload')
        blocks.append((flags, target, size, argument, data[offset:offset+count]))
        offset += count
        if flags & 0x8000:
            final = True
            break
    if not final:
        raise BackendError('Blackfin boot stream has no FINAL block')
    return blocks


class BlackfinPort:
    """Explicit experimental DSP endpoint. Unready or failed sessions never read as zero."""
    def __init__(self, worker, *, ready_address=0xFF9031D8, boot_steps=1000000,
                 timeout=5, operating=False, rom=None, boot_timeout=300):
        BlackfinBackend._span(ready_address, 4)
        if ready_address & 3 or not isinstance(boot_steps, int) or not 1 <= boot_steps <= 500000000:
            raise ValueError('aligned readiness word and bounded initialization budget required')
        if not isinstance(boot_timeout, (int, float)) or not math.isfinite(boot_timeout) or boot_timeout <= 0:
            raise ValueError('a finite positive native startup deadline is required')
        self.worker, self.timeout, self.operating = worker, timeout, operating
        self.rom = rom
        self.ready_address, self.boot_steps = ready_address, boot_steps
        self.boot_timeout = boot_timeout
        self.backend = None
        self.loaded = self.initialized = False
        self.words, self.transfer = [], None
        self.boot_report = None
        self._initial_word = bytes(4)

    def boot(self, stream):
        self.close()
        blocks = boot_blocks(stream)
        self.backend = BlackfinBackend(self.worker, timeout=self.timeout, operating=self.operating, rom=self.rom)
        try:
            for flags, target, size, argument, data in blocks:
                if flags & (0x800 | 0x1000):
                    continue
                for offset in range(0, size, LIMIT):
                    count = min(size-offset, LIMIT)
                    chunk = (struct.pack('<I', argument)*((count+3)//4))[:count] if flags & 0x100 else data[offset:offset+count]
                    self.backend.write(target+offset, chunk)
            self._initial_word = self.backend.read(self.ready_address, 4)
            self.loaded = True
            self.backend.set_register(53, 0xFFA00000)
            self.service(16)
        except (ValueError, BackendError):
            self.close()
            raise

    def _require_loaded(self):
        if (not self.loaded or self.backend is None or self.backend.process is None
                or self.backend.process.poll() is not None):
            raise BackendError('Blackfin DSP program is not loaded')

    def service(self, steps=64):
        self._require_loaded()
        try:
            result = self.backend.run(steps)
            value = self.backend.read(self.ready_address, 4)
            self.initialized = value != self._initial_word and value != bytes(4)
            return result
        except BackendError:
            self.close()
            raise

    def wait_ready(self):
        self._require_loaded()
        steps = 0
        deadline = time.monotonic() + self.boot_timeout
        try:
            while steps < self.boot_steps and not self.initialized:
                if time.monotonic() >= deadline:
                    raise BackendError('Blackfin native startup deadline exceeded')
                count = self.service(min(10000, self.boot_steps-steps))['steps']
                if count <= 0:
                    raise BackendError('Blackfin initialization made no execution progress')
                steps += count
            value = self.backend.read(self.ready_address, 4)
            self.boot_report = dict(steps=steps, pc=self.backend.register(53),
                                    ready_address=self.ready_address, before=self._initial_word.hex(), after=value.hex(),
                                    ready=self.initialized, operating=self.operating,
                                    registers={name: self.backend.register(number) for name, number in
                                               (('R0', 0), ('P0', 8), ('P1', 9), ('SP', 14),
                                                ('SEQSTAT', 47), ('RETI', 49), ('RETX', 50))})
            if not self.initialized:
                raise BackendError(f'Blackfin initialization did not produce a response: {self.boot_report}')
            return self.boot_report
        except BackendError:
            self.close()
            raise

    def _abort(self, message):
        self.close()
        raise BackendError(message)

    def status(self):
        self._require_loaded()
        self.service()
        # Endpoint transport readiness, not calibrated DSP BUSY timing.
        return 0x85

    def control(self, value):
        self._require_loaded()
        value &= 65535
        if not self.words and value == 0x2C:
            return
        if self.transfer and self.transfer['left']:
            self._abort('Blackfin host transfer ended short')
        self.words.append(value)
        if len(self.words) == 7:
            command, lo, hi, count, width, a, b = self.words
            self.words = []
            if command not in (0xA9, 0xAB) or not count or (width, a, b) != (2, 0, 0):
                self._abort('invalid Blackfin host transfer')
            address = hi << 16 | lo
            try:
                BlackfinBackend._span(address, count*2)
            except ValueError:
                self._abort('invalid Blackfin host memory span')
            self.transfer = dict(command=command, address=address, left=count, data=bytearray())
            if command == 0xA9:
                self.service()
                self.transfer['data'] = self.backend.read(address, count*2)
                self.transfer['cursor'] = 0

    def write_word(self, value):
        self._require_loaded()
        transfer = self.transfer
        if transfer is None or not transfer['left'] or transfer['command'] != 0xAB:
            self._abort('Blackfin host write without a write transfer')
        transfer['data'].extend(struct.pack('<H', value & 65535))
        transfer['left'] -= 1
        if not transfer['left']:
            self.backend.write(transfer['address'], transfer['data'])
            self.service()

    def read_word(self):
        self._require_loaded()
        transfer = self.transfer
        if transfer is None or not transfer['left'] or transfer['command'] != 0xA9:
            self._abort('Blackfin host read without a read transfer')
        value = struct.unpack_from('<H', transfer['data'], transfer['cursor'])[0]
        transfer['cursor'] += 2
        transfer['address'] += 2
        transfer['left'] -= 1
        return value

    def close(self):
        self.loaded = self.initialized = False
        self.words, self.transfer = [], None
        if self.backend is not None:
            self.backend.close()
            self.backend = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
