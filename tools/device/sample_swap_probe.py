"""Time a reversible rewrite of one loaded synthetic user sample.

Default is an offline plan without MIDI. Hardware requires --execute, the own
--vsb, an expendable --slot (501..999), --unused-confirmed and exactly one of
--stopped-confirmed or --playback-confirmed. Start stopped at 1 KiB. Record
other voices and new note onsets externally during subsequent playback runs.
No card or flash API is used. An Execute timeout never causes an automatic
retry or cleanup while the stub might still run.
"""
import argparse
import json
import secrets
import struct
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "patch"))
import arm

STUB = 0xC1000000
BACKUP, VERIFY = 0xC274F000, 0xC275F000
READ, WRITE = 0xC004EDDC, 0xC004EF28
TIMER, TIMER_HZ = 0x01F0D000, 150_000_000
OS_TICK = 0xC06A292C
META, PLAYBACK, NAMES, CURSOR = 0xC036AD88, 0xC0362EE8, 0xC047B080, 0xC00F9C80
MAGIC = 0x53574150
SPANS = ((0xC00141F8, 0xD10), (READ, 0x14), (WRITE, 0x6C))


def enc(data):
    out = []
    for at in range(0, len(data), 7):
        block = data[at:at + 7]
        out.append(sum((v >> 7) << k for k, v in enumerate(block)))
        out.extend(v & 127 for v in block)
    return out


def dec(data):
    out = bytearray()
    for at in range(0, len(data), 8):
        block = data[at:at + 8]
        out.extend(v | ((block[0] >> k & 1) << 7) for k, v in enumerate(block[1:]))
    return bytes(out)


class Link:
    def __init__(self, ask, channel, model):
        if model != 0x24:
            raise ValueError("only the red Sampler supports this test")
        self.ask = ask
        self.largest = 1024
        self.head = [0x42, 0x30 + channel, 0, 1, model]

    def call(self, func, body, reply):
        raw = self.ask([0xF0, *self.head, func, *enc(body), 0xF7])
        if raw[:7] != [0xF0, *self.head, reply] or raw[-1:] != [0xF7]:
            raise ValueError("unexpected BLECH reply")
        return dec(raw[7:-1])

    def info(self):
        raw = self.call(0x60, b"", 0x68)
        if len(raw) != 24:
            raise ValueError("unknown BLECH INFO layout")
        status, version, flags, largest, _, _ = struct.unpack("<6I", raw)
        if status or version != 1 or flags & 0x47 != 0x47 or not 1024 <= largest <= 32768:
            raise ValueError("BLECH v1 with CRC read/write and EXEC required")
        self.largest = largest
        return largest

    def read(self, addr, count):
        if count > self.largest:
            return b"".join(self.read(addr + at, min(self.largest, count - at))
                            for at in range(0, count, self.largest))
        raw = self.call(0x61, struct.pack("<II", addr, count), 0x69)
        if len(raw) < 16:
            raise ValueError("truncated READ")
        status, got_addr, length, crc = struct.unpack_from("<4I", raw)
        data = raw[16:]
        if status or (got_addr, length) != (addr, count) or len(data) != count or zlib.crc32(data) != crc:
            raise ValueError("READ range, status or CRC mismatch")
        return data

    def write(self, data):
        crc = zlib.crc32(data)
        raw = self.call(0x62, struct.pack("<3I", STUB, len(data), crc), 0x6A)
        if raw != struct.pack("<3I", 0, STUB, len(data)):
            raise ValueError("WRITE BEGIN refused")
        raw = self.call(0x63, data, 0x6B)
        if raw != struct.pack("<4I", 0, STUB, len(data), crc):
            raise ValueError("WRITE DATA status, range or CRC mismatch")
        if self.read(STUB, len(data)) != data:
            raise ValueError("stub readback differs")

    def execute(self, run_id):
        raw = self.call(0x6F, struct.pack("<II", STUB, run_id), 0x70)
        if raw != struct.pack("<3I", 0, STUB, MAGIC):
            raise ValueError("EXEC did not confirm return")


def target(meta, cursor, length):
    if len(meta) != 0x45C or meta[11] != 1:
        raise ValueError("target slot is not loaded")
    offset, pcm = struct.unpack_from("<II", meta)
    if not 1024 <= length <= 65536 or length % 32 or offset % 32 or pcm < length:
        raise ValueError("target must contain the requested aligned PCM span")
    if not 0x365EC0 <= offset < cursor <= 0x01C65EC0 or offset + pcm > cursor:
        raise ValueError("target is outside the current DSP allocation cursor")
    return offset


def elapsed(before, after, period):
    return after - before if after >= before else after - before + period + 1


def stub(length, offset, run_id):
    text = f"""
    b start
result:
    .word {run_id}, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
start:
    push {{r4-r11, r12, lr}}
    ldr r4, =result
    ldr r1, [r4]
    cmp r0, r1
    bne invalid
    ldr r5, ={BACKUP}
    ldr r6, ={VERIFY}
    ldr r7, ={offset}
    ldr r8, ={length // 2}
    ldr r9, ={READ}
    ldr r10, ={WRITE}
    ldr r11, ={TIMER}
    mov r0, #1
    str r0, [r4, #4]
    ldr r0, [r11, #0x18]
    str r0, [r4, #16]
    ldr r1, ={TIMER_HZ - 1}
    cmp r0, r1
    blo failed
    ldr r0, [r11, #0x20]
    str r0, [r4, #20]
    tst r0, #0x80
    beq failed
    ldr r0, [r11, #0x24]
    str r0, [r4, #24]
    tst r0, #1
    beq failed
    mov r0, r5
    mov r1, r6
    mov r2, r8, lsr #1
    ldr r3, =0xa5a5a5a5
    ldr r12, =0x5a5a5a5a
prefill:
    str r3, [r0], #4
    str r12, [r1], #4
    subs r2, r2, #1
    bne prefill
    mov r0, r5
    mov r1, r7
    mov r2, r8
    blx r9
    mov r0, r6
    mov r1, r7
    mov r2, r8
    blx r9
    mov r0, #0
    bl compare
    cmp r0, #0
    bne failed
    mov r0, #1
    str r0, [r4, #36]
    ldr r0, =0x01010101
    bl copy
    ldr r0, ={OS_TICK}
    ldr r0, [r0]
    str r0, [r4, #28]
    ldr r0, [r11, #0x10]
    str r0, [r4, #8]
    mov r0, r6
    mov r1, r7
    mov r2, r8
    blx r10
    ldr r0, [r11, #0x10]
    str r0, [r4, #12]
    ldr r0, ={OS_TICK}
    ldr r0, [r0]
    str r0, [r4, #32]
    mov r0, #2
    str r0, [r4, #36]
    mov r0, #0
    bl copy
    mov r0, r6
    mov r1, r7
    mov r2, r8
    blx r9
    ldr r0, =0x01010101
    bl compare
    str r0, [r4, #44]
    str r1, [r4, #52]
    mov r0, r5
    mov r1, r7
    mov r2, r8
    blx r10
    mov r0, #3
    str r0, [r4, #36]
    ldr r0, =0x01010101
    bl copy
    mov r0, r6
    mov r1, r7
    mov r2, r8
    blx r9
    mov r0, #0
    bl compare
    str r0, [r4, #48]
    b finish
failed:
    mov r0, #1
    str r0, [r4, #48]
finish:
    ldr r12, [r4, #48]
    cmp r12, #0
    beq clear_prepare
    ldr r12, [r4, #36]
    cmp r12, #2
    movlo r12, #0
    movhs r12, #1
clear_prepare:
    mov r0, r5
    mov r1, r6
    mov r2, r8, lsr #1
    mov r3, #0
clear:
    cmp r12, #0
    streq r3, [r0]
    add r0, r0, #4
    str r3, [r1], #4
    subs r2, r2, #1
    bne clear
    ldr r0, ={MAGIC}
    str r0, [r4, #4]
    pop {{r4-r11, r12, pc}}
invalid:
    mov r0, #0
    pop {{r4-r11, r12, pc}}
compare:
    push {{r7, r10, r11, lr}}
    mov r7, r0
    mov r0, #0
    mov r1, #0
    mov r2, r5
    mov r3, r6
    mov r10, r8, lsr #1
compare_loop:
    ldr r11, [r2], #4
    eor r11, r11, r7
    add r1, r1, r11
    ldr r12, [r3], #4
    cmp r11, r12
    addne r0, r0, #1
    subs r10, r10, #1
    bne compare_loop
    pop {{r7, r10, r11, pc}}
copy:
    mov r1, r5
    mov r2, r6
    mov r3, r8, lsr #1
copy_loop:
    ldr r12, [r1], #4
    eor r12, r12, r0
    str r12, [r2], #4
    subs r3, r3, #1
    bne copy_loop
    bx lr
"""
    image = arm.assemble(text, STUB)
    if len(image.bytes) > 1024:
        raise ValueError("stub exceeds BLECH EXEC window")
    return image.bytes, image.symbols


def arguments(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--vsb", type=Path)
    p.add_argument("--slot", type=int)
    p.add_argument("--kib", type=int, default=1)
    p.add_argument("--unused-confirmed", action="store_true")
    p.add_argument("--stopped-confirmed", action="store_true")
    p.add_argument("--playback-confirmed", action="store_true")
    p.add_argument("--json", type=Path)
    p.add_argument("--make-wav", type=Path)
    a = p.parse_args(argv)
    if not 1 <= a.kib <= 64 or a.slot is not None and not 501 <= a.slot <= 999:
        raise ValueError("--kib must be 1..64 and --slot must be 501..999")
    if a.execute and (a.plan or not a.vsb or a.slot is None or not a.unused_confirmed or
                      a.stopped_confirmed == a.playback_confirmed or a.make_wav):
        raise ValueError("execution requires --vsb, --slot, --unused-confirmed and exactly one state confirmation")
    return a


def make_wav(path, length):
    import wave
    output = path.resolve()
    if any((parent / ".git").exists() for parent in output.parents):
        raise ValueError("write the generated test WAV outside every repository")
    pcm = b"".join(struct.pack("<h", ((i * 97) & 4095) - 2048) for i in range(length // 2))
    with wave.open(str(output), "wb") as wav:
        wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
        wav.writeframes(pcm)


def own_firmware(path):
    sys.path.insert(0, str(HERE.parent / "emu"))
    from firmware import identify
    data = path.read_bytes()
    if len(data) != 0x200100:
        raise ValueError("expected the own 2.02 VSB including its 0x100-byte header")
    profile = identify(data[0x100:])
    if profile.build not in ("stock", "hacktribe") or profile.moved:
        raise ValueError("only the measured Sampler stock/hacktribe addresses are supported")
    return data, profile.build


def identity_target(link, slot):
    index = slot - 1
    name = link.read(NAMES + index * 32, 32)
    key = struct.unpack_from("<H", name, 30)[0] - 50
    if not 0 <= key < 1000:
        raise ValueError("sample import mapping is outside the measured table")
    chain = []
    for base, stride, field in ((0xC035738C, 32, 16), (0xC035F06C, 16, 8), (0xC0350644, 8, 2)):
        address = base + key * stride + field
        raw = link.read(address, 2)
        chain.append((address, raw))
        key = struct.unpack("<H", raw)[0]
        if key >= 1000:
            raise ValueError("sample mapping has an invalid index")
    if key != index:
        raise ValueError("this probe requires an identity-mapped target slot")
    meta = link.read(META + index * 0x45C, 0x45C)
    if struct.unpack_from("<H", meta, 22)[0] != index:
        raise ValueError("sample metadata index differs from the resolved slot")
    return chain


def run(link, firmware, slot, length, mode):
    link.info()
    for addr, count in SPANS:
        start = addr - 0xC0000000 + 0x100
        if link.read(addr, count) != firmware[start:start + count]:
            raise ValueError(f"live firmware differs at {addr:#x}; nothing written")
    index = slot - 1
    chain = identity_target(link, slot)
    ranges = ((META + index * 0x45C, 0x45C), (PLAYBACK + index * 16, 16),
              (NAMES + index * 32, 32), (CURSOR, 4))
    before = [link.read(addr, count) for addr, count in ranges]
    offset = target(before[0], struct.unpack("<I", before[3])[0], length)
    for base in (BACKUP, VERIFY):
        for at in range(0, length, 4096):
            if any(link.read(base + at, min(4096, length - at))):
                raise ValueError("scratch RAM is not zero; nothing written")
    run_id = secrets.randbits(31) | 1
    image, _ = stub(length, offset, run_id)
    original = link.read(STUB, len(image))
    link.write(image)
    # A missing reply may leave code running. No cleanup is sent in that case.
    started = time.monotonic()
    try:
        link.execute(run_id)
    except (Exception, SystemExit, KeyboardInterrupt) as error:
        raise RuntimeError("EXEC completion unconfirmed; no retry or cleanup sent; restart the device") from error
    execute_seconds = time.monotonic() - started
    words = struct.unpack("<14I", link.read(STUB + 4, 56))
    if words[0] != run_id or words[1] != MAGIC:
        raise RuntimeError("completion marker differs; restart the device, no cleanup sent")
    link.write(original)
    if words[12]:
        if words[9] < 2:
            raise RuntimeError("timer or backup verification failed before any DSP write")
        raise RuntimeError("restoration unverified; backup retained in RAM at 0xC274F000; restart the device")
    if words[11]:
        raise RuntimeError("changed transfer verification failed; original bytes restored and verified")
    for (addr, count), old in zip(ranges, before):
        if link.read(addr, count) != old:
            raise RuntimeError("sample metadata or allocation cursor changed")
    if any(link.read(address, 2) != raw for address, raw in chain):
        raise RuntimeError("sample mapping changed")
    ticks = elapsed(words[2], words[3], words[4])
    os_ms = (words[8] - words[7]) & 0xFFFFFFFF
    if not ticks or ticks > TIMER_HZ // 2 or os_ms > 500 or execute_seconds >= (words[4] + 1) / TIMER_HZ:
        raise RuntimeError("timer interval is ambiguous or over 500 ms; no throughput reported")
    return dict(mode=mode, slot=slot, bytes=length, ticks=ticks, timer_hz=TIMER_HZ,
                milliseconds=ticks / TIMER_HZ * 1000, kib_per_second=length / 1024 * TIMER_HZ / ticks,
                os_milliseconds=os_ms, checksum32=words[13], dsp_bytes_equal=True, target_tables_equal=True,
                audio_verified=False, limit_verified=False)


def main(argv=None):
    a = arguments(argv)
    if a.make_wav:
        make_wav(a.make_wav, a.kib * 1024)
        print(f"generated {a.kib} KiB synthetic PCM outside the repository; no device contact")
        return
    if not a.execute:
        print(json.dumps(dict(mode="offline plan", device="no device contact", bytes=a.kib * 1024,
                              target_slot=a.slot, needs="expendable loaded synthetic slot; stopped test before playback",
                              open=["real DSP throughput", "playback and note-on continuity", "physical DSP capacity"]), indent=2))
        return
    firmware, build = own_firmware(a.vsb)
    from led_show import mido_ask
    ask = mido_ask()
    found = ask([0xF0, 0x42, 0x50, 0, 0, 0xF7])
    if len(found) < 8 or found[:4] != [0xF0, 0x42, 0x50, 1]:
        raise ValueError("no Electribe discovery reply")
    result = run(Link(ask, found[4] & 15, found[6]), firmware, a.slot, a.kib * 1024,
                 "other voices playing" if a.playback_confirmed else "stopped")
    result["build"] = build
    output = json.dumps(result, indent=2)
    print(output)
    if a.json:
        a.json.write_text(output + "\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, TimeoutError, OSError) as error:
        raise SystemExit(str(error))
