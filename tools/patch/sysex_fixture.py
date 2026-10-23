"""Native SysEx command fixture with modeled firmware ABI calls and guarded RAM."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = 0xc3000000
TARGET_END = 0xc019a400
SIZES = (0, 1, 2, 6, 7, 8, 63, 64, 127, 255, 256, 4096, 8192, *range(32762, 32770))


def generator(path=None):
    path = Path(path or ROOT / 'tools/patch/blech_sysex.py')
    module_spec = importlib.util.spec_from_file_location('sysex_fixture_generator', path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def payload(length, offset=0):
    return bytes(((i * 73) ^ (i >> 3) ^ 0xa5) & 255 for i in range(offset, offset + length))


def encode(data):
    out = bytearray()
    for at in range(0, len(data), 7):
        group = data[at:at + 7]
        out.append(sum((v >> 7) << bit for bit, v in enumerate(group)))
        out.extend(v & 127 for v in group)
    return bytes(out)


def decode(data):
    out = bytearray()
    for at in range(0, len(data), 8):
        group = data[at:at + 8]
        out.extend(v | (((group[0] >> bit) & 1) << 7) for bit, v in enumerate(group[1:]))
    return bytes(out)


def protection(build):
    source = "import {protectTable} from './src/sysex-table.mjs'; console.log(Buffer.from(protectTable({build:process.argv[1]}).bytes).toString('hex'));"
    return bytes.fromhex(subprocess.check_output(['node', '--input-type=module', '-e', source, build], cwd=ROOT, text=True).strip())


class NativeSysex:
    def __init__(self, spec=None, build='hacktribe', table=None, freed_start=None):
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_BLOCK, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
        from unicorn import arm_const as registers
        self.a = registers
        self.spec = spec or generator()
        b = self.spec
        self.code_at, self.code, self.symbols = b.build_code()
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(0xc0000000, 0x4000000)
        self.uc.mem_write(self.code_at, self.code)
        self.uc.mem_write(b.TABLE_AT, table if table is not None else protection(build))
        self.build = build
        self.message, self.panel, self.folder_at = 0xc0100000, 0xc0101000, 0xc0102000
        self.stack, self.stop = 0xc200f000, 0xc3fff000
        self.folder = 'SD:KORG/' + ('electribe/' if build == 'synth' else 'blechtribe/')
        self.files = {}
        self.open_name, self.position = None, 0
        self.port, self.locked = 1, False
        self.sent, self.io, self.trace = [], [], []
        self.instructions = 0
        self.failures = {}
        self.short_read = self.short_write = None
        self.corrupt_read = False
        self.fallback = []
        self.write_word(b.PANEL, self.panel)
        self.uc.mem_write(self.folder_at, self.folder.encode() + b'\0')
        self.uc.mem_write(b.CHANNEL, b'\x03')
        start = b.BUF_END if freed_start is None else freed_start
        self.guards = [(b.STATE - 32, b'\xa6' * 32),
                       (start, b'\xd3' * (b.FILE_AREA - start)),
                       (b.FILE_AREA_END, b'\x5a' * 32)]
        for address, data in self.guards:
            if data:
                self.uc.mem_write(address, data)
        self.abi = {getattr(b, name): name for name in (
            'PORT_OF', 'TX_BEGIN', 'TX_SEND', 'TX_END', 'FLASH_OBJ', 'FLASH_READ',
            'FS_OPEN', 'FS_READ', 'FS_WRITE', 'FS_CLOSE', 'FS_LSEEK', 'FOLDER', 'STRING_FREE',
            'CLASSIFY_BACK', 'PROCESS_BACK')}
        for address in self.abi:
            self.uc.hook_add(UC_HOOK_CODE, self.external, begin=address, end=address)
        self.uc.hook_add(UC_HOOK_BLOCK, self.block)
        self.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self.memory)
        self.uc.ctl_flush_tb()
        self.reset()

    def reset(self):
        b = self.spec
        self.uc.mem_write(b.STATE, bytes(b.STATE_END - b.STATE))
        self.uc.mem_write(b.FILE_AREA, bytes(b.FILE_AREA_END - b.FILE_AREA))
        self.uc.mem_write(b.BUF, bytes(min(b.BUF_END, min((a for a, g in self.guards if g and a >= b.BUF), default=b.BUF_END)) - b.BUF))
        self.uc.mem_write(SCRATCH - 16, b'\x91' * 16 + payload(b.MAX_BLOCK) + b'\x92' * 16)
        self.sent.clear()

    def block(self, _uc, address, size, _data):
        if self.code_at <= address < self.code_at + len(self.code):
            self.instructions += size // 4

    def memory(self, _uc, _access, address, size, _value, _data):
        for start, data in self.guards:
            if data and address < start + len(data) and start < address + size:
                raise AssertionError(f'native access to guard at {address:#x}+{size}')

    def check_guards(self):
        for address, data in self.guards:
            if data and bytes(self.uc.mem_read(address, len(data))) != data:
                raise AssertionError(f'guard changed at {address:#x}')
        if bytes(self.uc.mem_read(SCRATCH - 16, 16)) != b'\x91' * 16 or bytes(self.uc.mem_read(SCRATCH + self.spec.MAX_BLOCK, 16)) != b'\x92' * 16:
            raise AssertionError('RAM transfer changed a guard')

    def read_word(self, address):
        return struct.unpack('<I', self.uc.mem_read(address, 4))[0]

    def write_word(self, address, value):
        self.uc.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def cstring(self, address):
        return bytes(self.uc.mem_read(address, 128)).split(b'\0')[0].decode('ascii')

    def call(self, name, *args):
        a = self.a
        self.uc.reg_write(a.UC_ARM_REG_SP, self.stack)
        self.uc.reg_write(a.UC_ARM_REG_LR, self.stop)
        for i, value in enumerate(args):
            self.uc.reg_write(getattr(a, f'UC_ARM_REG_R{i}'), value)
        self.uc.emu_start(self.symbols[name], self.stop, count=20000000)
        if self.uc.reg_read(a.UC_ARM_REG_PC) != self.stop:
            raise AssertionError(f'{name} did not return')
        if self.uc.reg_read(a.UC_ARM_REG_SP) != self.stack:
            raise AssertionError(f'{name} changed SP')
        self.check_guards()
        return self.uc.reg_read(a.UC_ARM_REG_R0)

    def external(self, uc, address, _size, _data):
        a, b = self.a, self.spec
        args = [uc.reg_read(getattr(a, f'UC_ARM_REG_R{i}')) for i in range(4)]
        name = self.abi[address]
        result = 0
        if name == 'PORT_OF':
            result = self.port
        elif name == 'TX_BEGIN':
            if self.locked:
                raise AssertionError('nested TX lock')
            self.locked = True
        elif name == 'TX_END':
            if not self.locked:
                raise AssertionError('TX lock missing')
            self.locked = False
        elif name == 'TX_SEND':
            _, pointer, length, port = args
            if not self.locked or port != self.port:
                raise AssertionError('reply uses wrong port or no TX lock')
            if not (b.BUF <= pointer < pointer + length <= b.BUF_END or b.STATE <= pointer < pointer + length <= b.STATE_END):
                raise AssertionError('reply leaves its declared buffer')
            chunks, at = [], 0
            while at < length:
                count = min((1, 6, 7, 8, 63, 64, 127)[len(chunks) % 7], length - at)
                chunks.append(bytes(uc.mem_read(pointer + at, count)))
                at += count
            self.sent.append(b''.join(chunks))
        elif name == 'FLASH_OBJ':
            result = self.panel
        elif name == 'FLASH_READ':
            _, destination, offset, length = args
            self.buffer_range(destination, length)
            self.io.append([name, offset, length])
            result = 0 if self.failures.get(name) else 1
            if result:
                uc.mem_write(destination, payload(length, offset))
        elif name == 'FOLDER':
            if args[1] != b.FOLDER_ID:
                raise AssertionError('wrong update folder id')
            self.write_word(args[0], self.folder_at)
        elif name == 'FS_OPEN':
            file_object, path, mode = args[:3]
            path = self.cstring(path)
            self.io.append([name, path, mode])
            result = self.failures.get(name, 0)
            if not result:
                if mode & 8:
                    self.files[path] = bytearray()
                elif path not in self.files:
                    result = 4
                if not result:
                    self.open_name, self.position = path, 0
                    self.write_word(file_object + b.FIL_SIZE, len(self.files[path]))
        elif name == 'FS_LSEEK':
            self.io.append([name, args[1]])
            self.position = args[1]
            result = self.failures.get(name, 0)
        elif name in ('FS_READ', 'FS_WRITE'):
            _, pointer, length, count_at = args
            self.buffer_range(pointer, length)
            self.io.append([name, self.open_name, self.position, length])
            result = self.failures.get(name, 0)
            count = 0
            if not result:
                data = self.files[self.open_name]
                if name == 'FS_READ':
                    count = min(length, max(0, len(data) - self.position))
                    if self.short_read is not None:
                        count = min(count, self.short_read)
                    part = bytes(data[self.position:self.position + count])
                    if self.corrupt_read and part:
                        part = bytes([part[0] ^ 1]) + part[1:]
                    if part:
                        uc.mem_write(pointer, part)
                else:
                    count = min(length, self.short_write) if self.short_write is not None else length
                    data.extend(bytes(max(0, self.position + count - len(data))))
                    data[self.position:self.position + count] = uc.mem_read(pointer, count)
                self.position += count
            self.write_word(count_at, count)
        elif name == 'FS_CLOSE':
            self.io.append([name])
            result = self.failures.get(name, 0)
            self.open_name = None
        elif name == 'CLASSIFY_BACK':
            self.fallback.append(name)
            result = 0x7777
        elif name == 'PROCESS_BACK':
            self.fallback.append(name)
            sp = uc.reg_read(a.UC_ARM_REG_SP)
            values = struct.unpack('<8I', uc.mem_read(sp, 32))
            for i, value in enumerate(values[:7]):
                uc.reg_write(getattr(a, f'UC_ARM_REG_R{i}'), value)
            uc.reg_write(a.UC_ARM_REG_SP, sp + 32)
            uc.reg_write(a.UC_ARM_REG_PC, values[7])
            return
        uc.reg_write(a.UC_ARM_REG_R0, result)
        uc.reg_write(a.UC_ARM_REG_PC, uc.reg_read(a.UC_ARM_REG_LR))

    def buffer_range(self, address, length):
        b = self.spec
        if not b.BUF <= address <= address + length <= b.BUF_END:
            raise AssertionError('firmware ABI buffer leaves the declared area')

    def request(self, function, raw=b''):
        b = self.spec
        before = len(self.sent)
        self.uc.mem_write(self.message, bytes(32))
        accepted = self.call('classify_hook', self.message, function)
        if accepted == 0x1e:
            pointer, remaining = self.read_word(b.DESC), self.read_word(b.DESC + 4)
            if len(raw) != remaining:
                raise ValueError('native command fixture needs a complete decoded request')
            self.uc.mem_write(pointer, raw)
            self.write_word(b.DESC + 8, len(raw))
            self.call('process_hook', self.message)
        elif function == b.FUNC_INFO and not self.read_word(self.panel + 0x18) & b.KILL_SWITCH:
            self.call('process_hook', self.message)
        if len(self.sent) == before:
            return None
        frame = self.sent[-1]
        if frame[:6] != bytes([0xf0, 0x42, 0x33, 0, 1, b.MODEL]) or frame[-1] != 0xf7:
            raise AssertionError('invalid reply frame')
        if frame[6] != (b.REPLY_FBEGIN if function == b.FUNC_PBEGIN else function + 8):
            raise AssertionError('wrong reply function')
        raw_reply = decode(frame[7:-1])
        if encode(raw_reply) != frame[7:-1]:
            raise AssertionError('noncanonical 7-bit reply')
        self.trace.append([self.port, function, len(raw), hashlib.sha256(raw).hexdigest(), hashlib.sha256(frame).hexdigest()])
        self.check_guards()
        return raw_reply

    def words(self, function, *words):
        return self.request(function, struct.pack('<' + 'I' * len(words), *words))


def exercise(machine, sizes=SIZES, ports=(1, 2)):
    b = machine.spec
    for port in ports:
        machine.port = port
        info = machine.request(b.FUNC_INFO)
        status, version, flags, maximum, _table_crc, flash_maximum = struct.unpack('<6I', info)
        assert (status, version, flags, maximum, flash_maximum) == (0, 1, 0x3f, 32768, 4096)
        for length in sizes:
            machine.reset()
            data = payload(length)
            valid = 0 < length <= b.MAX_BLOCK
            read = machine.words(b.FUNC_READ, SCRATCH, length)
            status, address, count, crc = struct.unpack_from('<4I', read)
            assert status == (b.STATUS_OK if valid else b.STATUS_RANGE)
            if valid:
                assert address == SCRATCH and count == length and read[16:] == data and crc == zlib.crc32(data)
            begin = machine.words(b.FUNC_BEGIN, SCRATCH, length, zlib.crc32(data))
            status = struct.unpack_from('<I', begin)[0]
            expected = b.STATUS_RANGE if not valid else b.STATUS_REFUSED if machine.build == 'synth' else b.STATUS_OK
            assert status == expected
            if status == b.STATUS_OK:
                reply = machine.request(b.FUNC_DATA, data)
                assert struct.unpack('<4I', reply) == (b.STATUS_OK, SCRATCH, length, zlib.crc32(data))
                assert bytes(machine.uc.mem_read(SCRATCH, length)) == data
            flash = machine.words(b.FUNC_FLASH, 0x123457, length)
            good_flash = 0 < length <= b.FLASH_MAX
            assert struct.unpack_from('<I', flash)[0] == (b.STATUS_OK if good_flash else b.STATUS_RANGE)
            if good_flash:
                assert flash[16:] == payload(length, 0x123457)
                assert struct.unpack_from('<I', flash, 12)[0] == zlib.crc32(flash[16:])
            for which, filename in [(0, 'SYSTEM.VSB'), (b.FILE_OTHER, 'ORIGINAL.BIN')]:
                name = machine.folder + 'System/' + filename
                contents = payload(b.MAX_BLOCK + 40)
                machine.files[name] = bytearray(contents)
                reply = machine.words(b.FUNC_FREAD, which | 7, length)
                status, address, count, crc, size = struct.unpack_from('<5I', reply)
                assert status == (b.STATUS_OK if length <= b.MAX_BLOCK else b.STATUS_RANGE)
                if not status:
                    expected_data = contents[7:7 + length]
                    assert reply[20:] == expected_data and count == length and size == len(contents)
                    assert crc == zlib.crc32(expected_data)
                begin = machine.words(b.FUNC_FBEGIN, which, length, zlib.crc32(data))
                assert struct.unpack_from('<I', begin)[0] == (b.STATUS_OK if valid else b.STATUS_RANGE)
                if valid:
                    reply = machine.request(b.FUNC_DATA, data)
                    assert struct.unpack('<4I', reply) == (b.STATUS_OK, 0, length, zlib.crc32(data))
                    assert machine.files[name] == data
            name = b'0123456789abcdef'
            begin = machine.request(b.FUNC_PBEGIN, struct.pack('<III', 0, length, zlib.crc32(data)) + name)
            assert struct.unpack_from('<I', begin)[0] == (b.STATUS_OK if valid else b.STATUS_RANGE)
            if valid:
                reply = machine.request(b.FUNC_DATA, data)
                assert struct.unpack('<4I', reply) == (b.STATUS_OK, 0, length, zlib.crc32(data))
                assert machine.files['SD:KORG/blechtribe/Plugin/' + name.decode() + '.blech'] == data
            machine.check_guards()
    return {'instructions': machine.instructions, 'cases': len(machine.trace),
            'vectorsSha256': hashlib.sha256(json.dumps([row[:4] for row in machine.trace]).encode()).hexdigest(),
            'resultsSha256': hashlib.sha256(json.dumps(machine.trace).encode()).hexdigest(),
            'ioSha256': hashlib.sha256(json.dumps(machine.io).encode()).hexdigest()}
