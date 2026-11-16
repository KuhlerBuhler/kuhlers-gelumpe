# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, process-isolated access to the GNU Blackfin simulator worker."""
import ctypes
import mmap
import os
import math
from pathlib import Path
import pickle
import selectors
import socket
import struct
import subprocess
import sys
import tempfile
import time
from types import MappingProxyType

LIMIT = 1 << 20
CHANNEL_SPIN_NS = 200000   # how long a wait for the worker spins before it sleeps on the pipe
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


def _channel_library():
    """blackfin_channel.c built by native_build, or None: no C compiler, or BLECH_WORKER_CHANNEL=pipe."""
    if os.environ.get('BLECH_WORKER_CHANNEL') == 'pipe':
        return None
    import native_build
    lib = native_build.library(Path(__file__).resolve().parents[1] / 'dsp/blackfin_channel.c')
    if lib is not None and lib.blech_channel_size.restype is not ctypes.c_uint64:
        lib.blech_channel_size.restype = ctypes.c_uint64
        lib.blech_channel_ring.restype = ctypes.c_void_p
        lib.blech_channel_ring.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.blech_ring_write.restype = ctypes.c_int
        lib.blech_ring_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_int]
        lib.blech_ring_read.restype = ctypes.c_int64
        lib.blech_ring_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64,
                                        ctypes.c_int, ctypes.c_int64, ctypes.c_int64]
    return lib


class BlackfinBackend:
    def __init__(self, worker, *, timeout=5, operating=False, rom=None):
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('a finite positive Blackfin deadline is required')
        self._fields(timeout, rom, tempfile.TemporaryFile())
        channel_path = None
        try:
            path = Path(worker).resolve(strict=True)
            arguments = [str(path)] + (['--operating'] if operating else [])
            lib = _channel_library()
            if lib is not None:
                handle, channel_path = tempfile.mkstemp(prefix='blackfin-channel-')
                try:
                    os.ftruncate(handle, lib.blech_channel_size())
                    shared = mmap.mmap(handle, lib.blech_channel_size())
                finally:
                    os.close(handle)
                arguments += ['--channel', channel_path]
            self.process = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=self._stderr, bufsize=0)
            self._out, self._in = self.process.stdin.fileno(), self.process.stdout.fileno()
            os.set_blocking(self._out, False)
            os.set_blocking(self._in, False)
            self._selector.register(self._in, selectors.EVENT_READ)
            handshake = self._response()
            if handshake not in (b'BFIN9', b'BFIN9 channel'):
                raise BackendError('invalid Blackfin worker handshake; rebuild the SDK for BFIN9')
            if handshake == b'BFIN9 channel':      # a worker that ignores --channel stays on the pipes
                self._map(lib, shared)
        except (OSError, BackendError) as error:
            detail = self._diagnostic()
            self.close()
            raise BackendError(f'Blackfin worker: {error}{detail}') from error
        finally:
            if channel_path is not None:
                os.unlink(channel_path)

    def _fields(self, timeout, rom, stderr):
        self.process = None
        self.timeout = timeout
        self.rom = rom
        self._stderr = stderr
        self._selector = selectors.DefaultSelector()
        self._deadline = time.monotonic() + timeout
        self._buffer = bytearray()   # bytes the worker has sent beyond the current answer
        self._cycles = None          # worker clock as of the last advance; None after anything else moved it
        self._host = None            # HOSTDP status from the last advance; None after any other request
        self._channel = None         # shared-memory rings once the worker answered the handshake
        self._link = None            # the socket to a worker copy (fork); the pipes of `process` otherwise
        self._out = self._in = -1    # where requests go and answers come from, or the bells of the channel

    def _map(self, lib, shared):
        anchor = ctypes.c_char.from_buffer(shared)
        base = ctypes.addressof(anchor)
        self._channel = (lib, shared, anchor, lib.blech_channel_ring(base, 0), lib.blech_channel_ring(base, 1),
                         ctypes.create_string_buffer(LIMIT + 64))

    def fork(self):
        """A second backend whose worker is a copy of this one's as it is now (worker op 19): the same DSP
        memory, registers, devices, event queue and clock. Both go on independently from here; this one is
        left exactly as it was, so several cases can start from one boot."""
        if self.process is None and self._link is None:
            raise BackendError('Blackfin worker is closed')
        folder = tempfile.mkdtemp(prefix='bfin-', dir=None if len(tempfile.gettempdir()) < 64 else '/tmp')
        socket_path, channel_path = os.path.join(folder, 's'), None
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        copy = BlackfinBackend.__new__(BlackfinBackend)
        copy._fields(self.timeout, self.rom, os.fdopen(os.dup(self._stderr.fileno()), 'rb'))
        try:
            listener.bind(socket_path)
            listener.listen(1)
            shared = None
            if self._channel is not None:
                lib = self._channel[0]
                channel_path = os.path.join(folder, 'c')
                handle = os.open(channel_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    os.ftruncate(handle, lib.blech_channel_size())
                    shared = mmap.mmap(handle, lib.blech_channel_size())
                finally:
                    os.close(handle)
            spec = socket_path.encode() + b'\0' + (channel_path.encode() if channel_path else b'') + b'\0'
            copy.pid = struct.unpack('<I', self._request(19, 0, len(spec), spec))[0]
            listener.settimeout(self.timeout)
            copy._link, _ = listener.accept()
            copy._link.setblocking(False)
            copy._out = copy._in = copy._link.fileno()
            copy._selector.register(copy._in, selectors.EVENT_READ)
            if shared is not None:
                copy._map(self._channel[0], shared)
            if copy._response() != b'BFIN9 copy':
                raise BackendError('invalid Blackfin worker copy handshake')
            copy._cycles = self._cycles
        except (OSError, BackendError) as error:
            copy.close()
            raise BackendError(f'Blackfin worker copy: {error}') from error
        finally:
            listener.close()
            for path in (socket_path, channel_path):
                if path is not None and os.path.exists(path):
                    os.unlink(path)
            os.rmdir(folder)
        return copy

    def running(self):
        if self.process is None:
            return self._link is not None
        return self.process.poll() is None

    def after_fork(self):
        """Call in a child process (os.fork) that goes on with this backend: kqueue selectors are not inherited."""
        self._selector = selectors.DefaultSelector()
        self._selector.register(self._in, selectors.EVENT_READ)

    def _diagnostic(self):
        if self._stderr.closed:
            return ''
        self._stderr.seek(0, os.SEEK_END)
        self._stderr.seek(max(0, self._stderr.tell() - 2048))
        data = self._stderr.read().decode('utf8', errors='replace').strip()
        return f': {data}' if data else ''

    def _send(self, data):
        if self._channel is not None:
            lib, _, _, to_worker, _, _ = self._channel
            if lib.blech_ring_write(to_worker, data, len(data), self._out):
                raise BackendError('Blackfin worker stopped accepting requests')
            return
        # The pipe almost always has room: write first and wait only for a full pipe.
        try:
            count = os.write(self._out, data)
        except BlockingIOError:
            count = 0
        if count == len(data):
            return
        if count < 0:
            raise BackendError('Blackfin worker stopped accepting requests')
        view = memoryview(data)[count:]
        with selectors.DefaultSelector() as selector:
            selector.register(self._out, selectors.EVENT_WRITE)
            while view:
                remaining = self._deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise BackendError('Blackfin worker deadline exceeded while writing')
                try:
                    count = os.write(self._out, view)
                except BlockingIOError:
                    continue
                if count <= 0:
                    raise BackendError('Blackfin worker stopped accepting requests')
                view = view[count:]

    def _receive(self, size):
        # Reads whatever the worker has sent, so a header and its data usually cost one read;
        # waits only when nothing has arrived yet.
        data = self._buffer
        if self._channel is not None:
            lib, _, _, _, to_host, buffer = self._channel
            while len(data) < size:
                left_ms = int((self._deadline - time.monotonic()) * 1000)
                if left_ms <= 0:
                    raise BackendError('Blackfin worker deadline exceeded')
                count = lib.blech_ring_read(to_host, buffer, size - len(data), len(buffer),
                                            self._in, CHANNEL_SPIN_NS, left_ms)
                if count == 0:
                    raise BackendError('Blackfin worker exited before answering')
                if count == -1:
                    raise BackendError('Blackfin worker deadline exceeded')
                if count < 0:
                    raise BackendError('Blackfin worker channel failed')
                data.extend(memoryview(buffer)[:count])
        while len(data) < size:
            try:
                chunk = os.read(self._in, 65536)
            except BlockingIOError:
                remaining = self._deadline - time.monotonic()
                if remaining <= 0 or not self._selector.select(remaining):
                    raise BackendError('Blackfin worker deadline exceeded')
                continue
            if not chunk:
                raise BackendError('Blackfin worker exited before answering')
            data.extend(chunk)
        out = bytes(data[:size])
        del data[:size]
        return out

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
        if self.process is None and self._link is None:
            raise BackendError('Blackfin worker is closed')
        self._deadline = time.monotonic() + self.timeout
        self._host = None
        if op in (4, 5, 13):         # set_register can write CYCLES; run and the old advance move the clock untracked
            self._cycles = None
        try:
            self._send(struct.pack('<III', op, address, count) + data)
            response = self._response(rom=op in (5, 13, 18, 20))
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

    def watch_memory(self, address, size):
        if (not isinstance(address, int) or not isinstance(size, int) or not 0 <= size <= 0xFFFFFFFF
                or not 0 <= address <= 0xFFFFFFFF or address + size > 1 << 32):
            raise ValueError('invalid Blackfin memory observation window')
        self._request(16, address, size)

    def memory_accesses(self):
        values = struct.unpack('<8Q16I', self._request(17, 0, 0, extra=128))
        return {kind: dict(accesses=values[2 * i], bytes=values[2 * i + 1],
                           **dict(zip(('address', 'origin', 'descriptor', 'width'), values[8 + 4 * i:12 + 4 * i])))
                for i, kind in enumerate(('cpu_read', 'cpu_write', 'dma_read', 'dma_write'))}

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

    def host_status(self):
        if self._host is not None:
            return self._host
        return struct.unpack('<I', self._request(9, 0, 0, extra=4))[0]

    def host_control(self, word):
        self._host_word(10, word)

    def host_write(self, word):
        self._host_word(11, word)

    def host_read(self):
        return struct.unpack('<I', self._request(12, 0, 0, extra=4))[0]

    def host_frdy(self):
        return struct.unpack('<I', self._request(15, 0, 0, extra=4))[0]

    def clock_status(self):
        lo, hi, remaining, idle = struct.unpack('<4I', self._request(14, 0, 0, extra=16))
        return dict(cycles=lo | hi << 32, remaining=remaining, idle=bool(idle))

    def advance(self, cycles, ready_address=0):
        """Run `cycles` cycles. The answer also carries the HOSTDP status after them (kept for host_status())
        and, with `ready_address`, the 4 bytes there, so one ARM sync costs one round trip."""
        if not isinstance(cycles, int) or not 1 <= cycles <= 1000000:
            raise ValueError('invalid bounded Blackfin cycle budget')
        if not isinstance(ready_address, int) or not 0 <= ready_address <= 0xFFFFFFFC:
            raise ValueError('invalid Blackfin ready address')
        start = self._cycles if self._cycles is not None else self.clock_status()['cycles']
        left, steps, calls = cycles, 0, 0
        while left:
            try:
                answer = self._request(18, left, ready_address)
                if len(answer) != 24:
                    raise BackendError('invalid Blackfin advance answer')
                elapsed, executed, pc, idle, host = struct.unpack('<5I', answer[:20])
                if elapsed != left:
                    raise BackendError('Blackfin did not reach the requested time boundary')
                steps += executed
                self._cycles, self._host = start + cycles, host
                break
            except _ROMCall as error:
                steps += error.steps
                try:
                    if self.rom is None or calls >= 64:
                        raise BackendError('missing or exhausted Blackfin ROM service')
                    self.rom.handle(self, error.registers)
                    calls += 1
                    elapsed = self.clock_status()['cycles'] - start
                    if not 0 <= elapsed < cycles:
                        raise BackendError('invalid Blackfin ROM time boundary')
                    left = cycles - elapsed
                except (BackendError, ValueError) as failure:
                    self.close()
                    raise BackendError(f'{failure}: {error}') from failure
        return dict(cycles=cycles, steps=steps, pc=pc, idle=bool(idle), host_status=host,
                    word=answer[20:] if ready_address else None)

    def ahead(self, status, steps, ready_address=0, word=b''):
        """Runs advance(step) for the steps in turn, as long as the HOSTDP status stays `status` and, with
        `ready_address`, the 4 bytes there stay `word`, in one round trip (a polling ARM,
        Machine._poll_ahead). Returns the steps done and the status after the last of them; a change ends
        the steps with the one that made it. A ROM entry is served as in advance and the steps go on."""
        if ready_address and (not 0 < ready_address <= 0xFFFFFFFC or len(word) != 4):
            raise ValueError('invalid Blackfin ready address')
        if not steps or len(steps) > LIMIT // 4 - 2 or any(not 0 <= step <= 1000000 for step in steps):
            raise ValueError('invalid Blackfin poll steps')
        if self._cycles is None:
            self._cycles = self.clock_status()['cycles']
        done = 0
        while done < len(steps):
            start, rest = self._cycles, steps[done:]
            try:
                answer = self._request(20, len(rest), status, struct.pack(f'<I4s{len(rest)}I', ready_address,
                                                                          word or bytes(4), *rest))
            except _ROMCall as error:
                try:
                    if self.rom is None:
                        raise BackendError('missing Blackfin ROM service')
                    self.rom.handle(self, error.registers)
                    elapsed = self.clock_status()['cycles'] - start
                except (BackendError, ValueError) as failure:
                    self.close()
                    raise BackendError(f'{failure}: {error}') from failure
                for step in rest:            # the run the ROM entry came in, then finish it as advance does
                    if elapsed < step:
                        break
                    elapsed -= step
                    start += step
                    done += 1
                self._cycles = start + elapsed
                left = steps[done] - elapsed
                if left:
                    self.advance(left)
                host = self.host_status()
                done += 1
                if host != status or ready_address and self.read(ready_address, 4) != word:
                    return done, host
                continue
            if len(answer) != 12:
                raise BackendError('invalid Blackfin poll answer')
            ran, changed, host = struct.unpack('<3I', answer)
            if not 0 < ran <= len(rest) or (ran < len(rest) and not changed):
                raise BackendError('invalid Blackfin poll answer')
            done += ran
            self._cycles, self._host = start + sum(rest[:ran]), host
            if changed:
                break
        return done, self._host

    def _host_word(self, operation, word):
        if not isinstance(word, int) or not 0 <= word <= 65535:
            raise ValueError('invalid 16-bit HOSTDP bus word')
        self._request(operation, 0, word)

    def configure_sport(self, *, core_hz, input='silence', seed=1):
        if not isinstance(core_hz, int) or not 48000 <= core_hz <= 2000000000:
            raise ValueError('invalid SPORT0 test core frequency')
        if input not in ('silence', 'lcg') or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError('invalid SPORT0 input configuration')
        data = struct.pack('<4I', core_hz, 48000, input == 'lcg', seed)
        self._request(7, 0, len(data), data)

    def sport_status(self):
        names = ('core_hz', 'rate', 'input', 'seed', 'lcg_state', 'rx_frames', 'tx_frames',
                 'rx_words', 'tx_words', 'tx_hash', 'rx_fifo_words', 'tx_fifo_words')
        values = struct.unpack('<12I', self._request(8, 0, 0, extra=48))
        return dict(zip(names, values))

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
        link, self._link = self._link, None
        if link is not None:
            link.close()                # the copy reads the end of its requests and exits
        channel, self._channel = self._channel, None
        if channel is not None:
            shared = channel[1]
            del channel
            shared.close()
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
                 timeout=5, operating=False, rom=None, boot_timeout=300, sport=None,
                 host_transport='compatibility'):
        BlackfinBackend._span(ready_address, 4)
        if ready_address & 3 or not isinstance(boot_steps, int) or not 1 <= boot_steps <= 500000000:
            raise ValueError('aligned readiness word and bounded initialization budget required')
        if not isinstance(boot_timeout, (int, float)) or not math.isfinite(boot_timeout) or boot_timeout <= 0:
            raise ValueError('a finite positive native startup deadline is required')
        if host_transport not in ('compatibility', 'fifo') or (host_transport == 'fifo' and not operating):
            raise ValueError('FIFO transport requires operating mode; select compatibility or fifo explicitly')
        self.host_transport = host_transport
        self.worker, self.timeout, self.operating = worker, timeout, operating
        self.rom = rom
        self.sport = MappingProxyType(dict(sport)) if sport is not None else None
        self.ready_address, self.boot_steps = ready_address, boot_steps
        self.boot_timeout = boot_timeout
        self.backend = None
        self.loaded = self.initialized = False
        self.words, self.transfer = [], None
        self.boot_report = None
        self._initial_word = bytes(4)
        self.clock_bound = False
        self._boot_attempted = False
        self._clock_ns = self._clock_origin_ns = self._clock_cycles = 0

    def bind_clock(self, now_ns):
        if self.host_transport != 'fifo' or self.loaded or self.clock_bound or self.sport is None:
            raise ValueError('clock binding requires an unloaded FIFO transport with explicit SPORT clock')
        hz = self.sport.get('core_hz')
        if not isinstance(hz, int) or not 48000 <= hz <= 2000000000:
            raise ValueError('explicit bounded DSP core frequency is required')
        if not isinstance(now_ns, int) or now_ns < 0:
            raise ValueError('invalid common model time')
        self.clock_bound = True
        self._clock_hz = hz
        self._clock_ns = self._clock_origin_ns = now_ns

    def advance_to(self, now_ns):
        if not self.clock_bound or not isinstance(now_ns, int) or now_ns < self._clock_ns:
            raise ValueError('common model time cannot rewind')
        self._clock_ns = now_ns
        if not self.loaded:
            self._clock_origin_ns = now_ns
            return
        target = (now_ns - self._clock_origin_ns) * self._clock_hz // 1000000000
        value = None
        while self._clock_cycles < target:
            count = min(target - self._clock_cycles, 1000000)
            last = self._clock_cycles + count == target
            result = self.backend.advance(count, self.ready_address if last and not self.initialized else 0)
            if result['cycles'] != count:
                self._abort('Blackfin did not reach common model time')
            self._clock_cycles += count
            value = result['word']
        if not self.initialized:
            if value is None:
                value = self.backend.read(self.ready_address, 4)
            self.initialized = value != self._initial_word and value != bytes(4)
            if self.initialized:
                self.boot_report = dict(ready=True, ready_address=self.ready_address,
                                        before=self._initial_word.hex(), after=value.hex(),
                                        clock_cycles=self._clock_cycles, operating=self.operating,
                                        host_transport=self.host_transport)

    def ahead(self, status, steps, times):
        """advance_to(times[i]) with status() after each, as a polling ARM would, while the status stays
        `status` (BlackfinBackend.ahead). Returns how many were done and the status after the last."""
        if not self.clock_bound or not self.loaded or len(steps) != len(times) \
                or any(b < a for a, b in zip([self._clock_ns] + times, times)):
            raise ValueError('invalid poll steps')
        try:
            if self.initialized:
                done, host = self.backend.ahead(status, steps)
            else:                             # advance_to looks at the ready word after each step
                word = self.backend.read(self.ready_address, 4)
                done, host = self.backend.ahead(status, steps, self.ready_address, word)
        except BackendError:
            self.close()
            raise
        self._clock_cycles += sum(steps[:done])
        self._clock_ns = times[done - 1]
        if not self.initialized:
            value = self.backend.read(self.ready_address, 4)
            self.backend._host = host         # a read does not change the status it reports
            self.initialized = value != self._initial_word and value != bytes(4)
            if self.initialized:
                self.boot_report = dict(ready=True, ready_address=self.ready_address,
                                        before=self._initial_word.hex(), after=value.hex(),
                                        clock_cycles=self._clock_cycles, operating=self.operating,
                                        host_transport=self.host_transport)
        return done, host

    def frdy(self):
        if not self._boot_attempted and not self.loaded:
            return 1
        self._require_loaded()
        return self.backend.host_frdy()

    def boot(self, stream):
        self._boot_attempted = True
        self.close()
        blocks = boot_blocks(stream)
        self.backend = BlackfinBackend(self.worker, timeout=self.timeout, operating=self.operating, rom=self.rom)
        try:
            if self.sport is not None:
                self.backend.configure_sport(**self.sport)
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
            self._clock_cycles = 0
            self._clock_origin_ns = self._clock_ns
            if not self.clock_bound:
                self.service(16)
        except (ValueError, BackendError):
            self.close()
            raise

    def _require_loaded(self):
        if not self.loaded or self.backend is None or not self.backend.running():
            raise BackendError('Blackfin DSP program is not loaded')

    def service(self, steps=64):
        self._require_loaded()
        if self.clock_bound:
            raise BackendError('clock-bound DSP executes only through common model time')
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
                                    host_transport=self.host_transport,
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
        if not self.clock_bound:
            self.service()
        if self.host_transport == 'fifo':
            return self.backend.host_status()
        # Endpoint transport readiness, not calibrated DSP BUSY timing.
        return 0x85

    def control(self, value):
        self._require_loaded()
        if self.host_transport == 'fifo':
            self.backend.host_control(value)
            return
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
        if self.host_transport == 'fifo':
            self.backend.host_write(value)
            if not self.clock_bound:
                self.service()
            return
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
        if self.host_transport == 'fifo':
            if not self.clock_bound:
                self.service()
            return self.backend.host_read()
        transfer = self.transfer
        if transfer is None or not transfer['left'] or transfer['command'] != 0xA9:
            self._abort('Blackfin host read without a read transfer')
        value = struct.unpack_from('<H', transfer['data'], transfer['cursor'])[0]
        transfer['cursor'] += 2
        transfer['address'] += 2
        transfer['left'] -= 1
        return value

    def run_copy(self, task):
        """task() in a copy of this process (os.fork) whose DSP worker is a copy of this port's (fork), both as
        they are now, and what it returned (pickled across). The ARM machine, this port and its worker stay
        exactly as they were, so every case can start from the same boot: run_copy again for the next one."""
        copy = self.backend.fork()
        result_in, result_out = os.pipe()
        try:
            pid = os.fork()
        except OSError:
            copy.close()
            os.close(result_in)
            os.close(result_out)
            raise
        if pid == 0:                                    # the copy of this process
            outcome = ('error', 'case did not finish', '')
            try:
                os.close(result_in)
                copy.after_fork()
                self.backend = copy
                outcome = ('ok', task())
            except BaseException as error:
                import traceback
                outcome = ('error', f'{type(error).__name__}: {error}', traceback.format_exc())
            finally:
                try:
                    data = pickle.dumps(outcome, pickle.HIGHEST_PROTOCOL)
                except Exception as error:
                    data = pickle.dumps(('error', f'case result cannot be pickled: {error}', ''))
                try:
                    view = memoryview(data)
                    while view:
                        view = view[os.write(result_out, view):]
                    sys.stdout.flush()
                    sys.stderr.flush()
                finally:
                    os._exit(0)                         # never the parent's cleanup: its worker stays
        os.close(result_out)
        copy.close()                                    # the child holds its own end of the copy
        chunks = []
        with os.fdopen(result_in, 'rb') as stream:
            while chunk := stream.read(1 << 20):
                chunks.append(chunk)
        os.waitpid(pid, 0)
        status, *rest = pickle.loads(b''.join(chunks)) if chunks else ('error', 'case process died', '')
        if status != 'ok':
            raise BackendError(f'case in a process copy failed: {rest[0]}\n{rest[1]}'.rstrip())
        return rest[0]

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
