"""Read and write one small file on the card through the firmware's own FatFs.

RAM only: a stub of our own code goes to 0xC1000000 (Hacktribe's upload area),
runs once through the execute command 0x57, and writes its results into a free
scratch area at 0xC01F7000 that is read back and restored afterwards. Nothing
is flashed. The card gets two files in KORG/blechtribe/Plugin/: FSTEST.IN is
read (you put it there), FSTEST.OUT is created by the write test.

    python3 fatfs_probe.py --make-input DIR       # writes DIR/FSTEST.IN, the bytes the read test expects
    python3 fatfs_probe.py --emu VSB              # against the local emulator with a virtual card
    python3 fatfs_probe.py --dry-run              # on the laptop: checks only, writes nothing
    python3 fatfs_probe.py --read                 # on the laptop: read test
    python3 fatfs_probe.py --write                # on the laptop: read test, then create FSTEST.OUT
    python3 fatfs_probe.py --check-out FILE       # compare FSTEST.OUT taken from the card with what was sent
"""
import argparse
import hashlib
import json
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patch"))
from arm import assemble          # noqa: E402
from led_show import Device, emulator_ask, mido_ask, ICACHE_INVALIDATE, STUB_AT   # noqa: E402

FS_OPEN, FS_READ, FS_WRITE, FS_CLOSE = 0xC009DB60, 0xC009DD74, 0xC009DFB8, 0xC009E3DC
SCRATCH, SCRATCH_SIZE = 0xC01F7000, 0x500       # results at +0, FIL at +0x100, buffer at +0x400
FOLDER = "SD:KORG/blechtribe/Plugin/"
IN_NAME, OUT_NAME = "FSTEST.IN", "FSTEST.OUT"
MAGIC = 0x50524F42
PATTERN_LENGTH = 64
INPUT_SEED = b"gelumpe fatfs probe input 1"
EXPECTED = {                            # sha256 of the first 0x40 bytes of each routine in the measured build
    FS_OPEN: "ad7b970fbc00ed4172f53c3e30b19c48f965a8205f1cc074679ee7d449ae415c",
    FS_READ: "8278ac268d446b47cf3f9924be62c8ecdfc3a329c189537b2605f25b5837a87b",
    FS_WRITE: "28e1b6083443a28f7963a4e7b02882d213c951bed2b83f0e331a4436011afe0e",
    FS_CLOSE: "c6d44250d9acec0e044ab18218f593e23ba93291f2ebbf17207fca5d0e0cd2be",
}

SOURCE = """
.equ RES, 0xC01F7000
.equ FIL, 0xC01F7100
.equ BUF, 0xC01F7400
.equ FS_OPEN, 0xC009DB60
.equ FS_READ, 0xC009DD74
.equ FS_WRITE, 0xC009DFB8
.equ FS_CLOSE, 0xC009E3DC
start:
    push {r4-r11, lr}
    ldr r4, =RES
    ldr r5, =FIL
    ldr r6, =BUF
    mov r0, r5
    ldr r1, =path_in
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    str r0, [r4, #4]
    cmp r0, #0
    bne after_read
    mov r0, r5
    mov r1, r6
    mov r2, #256
    add r3, r4, #12
    ldr r12, =FS_READ
    blx r12
    str r0, [r4, #8]
    ldr r1, [r4, #12]
    mov r0, r6
    bl crc32
    str r0, [r4, #16]
    mov r0, r5
    ldr r12, =FS_CLOSE
    blx r12
    str r0, [r4, #20]
after_read:
    ldr r7, =data
    ldr r0, [r7]
    tst r0, #2
    beq finish
    mov r0, r5
    ldr r1, =path_out
    mov r2, #0x0A
    ldr r12, =FS_OPEN
    blx r12
    str r0, [r4, #24]
    cmp r0, #0
    bne finish
    mov r0, r5
    add r1, r7, #4
    mov r2, #PATTERN_LENGTH
    add r3, r4, #32
    ldr r12, =FS_WRITE
    blx r12
    str r0, [r4, #28]
    mov r0, r5
    ldr r12, =FS_CLOSE
    blx r12
    str r0, [r4, #36]
    mov r0, r5
    ldr r1, =path_out
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    str r0, [r4, #40]
    cmp r0, #0
    bne finish
    mov r0, r5
    mov r1, r6
    mov r2, #PATTERN_LENGTH
    add r3, r4, #48
    ldr r12, =FS_READ
    blx r12
    str r0, [r4, #44]
    mov r0, #1
    ldr r1, [r4, #48]
    cmp r1, #PATTERN_LENGTH
    bne compared
    mov r2, #0
    add r3, r7, #4
compare:
    ldrb r0, [r6, r2]
    ldrb r1, [r3, r2]
    cmp r0, r1
    movne r0, #1
    bne compared
    add r2, r2, #1
    cmp r2, #PATTERN_LENGTH
    blo compare
    mov r0, #0
compared:
    str r0, [r4, #52]
    mov r0, r5
    ldr r12, =FS_CLOSE
    blx r12
    str r0, [r4, #56]
finish:
    ldr r0, =MAGIC
    str r0, [r4]
    pop {r4-r11, pc}
crc32:
    mvn r2, #0
    ldr r12, =0xEDB88320
    add r1, r0, r1
crc_byte:
    cmp r0, r1
    bhs crc_done
    ldrb r3, [r0], #1
    eor r2, r2, r3
    mov r3, #8
crc_bit:
    movs r2, r2, lsr #1
    eorcs r2, r2, r12
    subs r3, r3, #1
    bne crc_bit
    b crc_byte
crc_done:
    mvn r0, r2
    bx lr
.pool
path_in:
    .asciz "SD:KORG/blechtribe/Plugin/FSTEST.IN"
path_out:
    .asciz "SD:KORG/blechtribe/Plugin/FSTEST.OUT"
.align 4
data:
"""


def input_bytes():
    """The file the read test expects: 200 bytes derived from a fixed seed."""
    out, block = b"", INPUT_SEED
    while len(out) < 200:
        block = hashlib.sha256(block).digest()
        out += block
    return out[:200]


def pattern_bytes(seed):
    """What the write test sends: 64 bytes from a per-run seed."""
    out, block = b"", seed
    while len(out) < PATTERN_LENGTH:
        block = hashlib.sha256(block).digest()
        out += block
    return out[:PATTERN_LENGTH]


def stub(mode, pattern):
    code = assemble(f".equ PATTERN_LENGTH, {PATTERN_LENGTH}\n.equ MAGIC, {MAGIC:#x}\n" + SOURCE, origin=STUB_AT)
    return code.bytes + struct.pack("<I", mode) + pattern


def results(raw):
    w = struct.unpack("<14I", raw[:56])
    return dict(magic=w[0], open_in=w[1], read_in=w[2], bytes_in=w[3], crc_in=w[4], close_in=w[5],
                open_out=w[6], write_out=w[7], bytes_out=w[8], close_out=w[9],
                open_back=w[10], read_back=w[11], bytes_back=w[12], compare=w[13])


def verdict(r, mode, want_in, pattern):
    """The result words against what the host expects. Returns a list of failures."""
    bad = []
    if r["magic"] != MAGIC:
        return ["the stub did not finish (no end marker)"]
    expected_crc = zlib.crc32(want_in) & 0xFFFFFFFF
    checks = [("open FSTEST.IN", r["open_in"] == 0), ("read FSTEST.IN", r["read_in"] == 0),
              ("length of FSTEST.IN", r["bytes_in"] == len(want_in)), ("CRC of FSTEST.IN", r["crc_in"] == expected_crc),
              ("close FSTEST.IN", r["close_in"] == 0)]
    if mode & 2:
        checks += [("create FSTEST.OUT", r["open_out"] == 0), ("write FSTEST.OUT", r["write_out"] == 0),
                   ("bytes written", r["bytes_out"] == len(pattern)), ("close after write", r["close_out"] == 0),
                   ("reopen FSTEST.OUT", r["open_back"] == 0), ("read back", r["read_back"] == 0),
                   ("bytes read back", r["bytes_back"] == len(pattern)), ("read back equals sent", r["compare"] == 0)]
    for name, ok in checks:
        if not ok:
            bad.append(name)
    return bad


def run(dev, mode, want_in, dry):
    original = dev.read(STUB_AT, 0x400)
    area = dev.read(SCRATCH, SCRATCH_SIZE)
    for address, digest in EXPECTED.items():
        if digest is not None and hashlib.sha256(dev.read(address, 0x40)).hexdigest() != digest:
            raise SystemExit(f"code at {address:#x} differs from the measured build; nothing written")
    panel = struct.unpack("<I", dev.read(0xC033E6FC, 4))[0]
    if not 0xC0000000 <= panel < 0xC4000000:
        raise SystemExit(f"panel object {panel:#x} not ready; nothing written")
    seed = struct.pack("<d", time.time())
    pattern = pattern_bytes(seed)
    code = stub(mode, pattern)
    if len(code) > 0x400:
        raise SystemExit(f"stub is {len(code)} bytes, the buffer holds 1024")
    print(f"checks passed: panel {panel:#x}, stub {len(code)} bytes, mode {mode} ({'read' if mode == 1 else 'read and write'})")
    print(f"FSTEST.IN expected: {len(want_in)} bytes, CRC-32 {zlib.crc32(want_in) & 0xFFFFFFFF:08x}")
    if dry:
        print("dry run: nothing written")
        return None
    try:
        dev.write(SCRATCH, bytes(SCRATCH_SIZE))
        dev.write(STUB_AT, code, verify=True)
        dev.execute(ICACHE_INVALIDATE)
        dev.execute(STUB_AT)
        raw, deadline = b"", time.monotonic() + 20
        while time.monotonic() < deadline:
            raw = dev.read(SCRATCH, 64)
            if struct.unpack("<I", raw[:4])[0] == MAGIC:
                break
            time.sleep(0.2)
        r = results(raw)
    finally:
        dev.write(STUB_AT, original)
        dev.write(SCRATCH, area)
        print("stub area and scratch area restored")
    bad = verdict(r, mode, want_in, pattern)
    print(json.dumps(r, indent=1))
    if mode & 2:
        print(f"FSTEST.OUT sent (hex): {pattern.hex()}")
    print("FAILED: " + ", ".join(bad) if bad else "all checks passed")
    return dict(result=r, failures=bad, pattern=pattern)


def emulator_with_card(vsb, input_data, seconds=3.0):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "emu"))
    import fat32
    from machine import Machine, UART1
    from sdcard import MemoryMedium, SDCard
    img = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(img)
    volume.write("/KORG/blechtribe/Plugin/" + IN_NAME, input_data)
    volume.close()
    m = Machine(open(vsb, "rb").read()[0x100:], None)
    m.insert_card(SDCard(MemoryMedium(img)))
    m.run_until(seconds)
    tx = m.uart[UART1]["tx"]

    def ask(message):
        start = len(tx)
        m.receive(UART1, message)
        deadline = m.time_ns + 3_000_000_000
        while m.time_ns < deadline:
            m.run_until(m.time_ns / 1e9 + 0.01)
            out = [b for b in tx[start:] if b < 0xF8]
            if out and out[-1] == 0xF7 and 0xF0 in out:
                return out[out.index(0xF0):]
            if m.asserts:
                raise SystemExit(f"emulator: firmware assertion {m.asserts[0]}")
        raise SystemExit("emulator: no answer")
    return ask, m, img, fat32


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--emu", metavar="VSB")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--read", action="store_true")
    p.add_argument("--write", action="store_true")
    p.add_argument("--make-input", metavar="DIR")
    p.add_argument("--check-out", metavar="FILE")
    a = p.parse_args()
    if a.make_input:
        target = Path(a.make_input) / IN_NAME
        target.write_bytes(input_bytes())
        print(f"wrote {target} ({len(input_bytes())} bytes, CRC-32 {zlib.crc32(input_bytes()) & 0xFFFFFFFF:08x})")
        return
    if a.check_out:
        print("compare by hand against the hex printed by the write test:", Path(a.check_out).read_bytes().hex())
        return
    mode = 3 if (a.write or a.emu) else 1
    if a.emu:
        ask, m, img, fat32 = emulator_with_card(a.emu, input_bytes())
        outcome = run(Device(ask), mode, input_bytes(), a.dry_run)
        if outcome and not a.dry_run:
            m.run_until(m.time_ns / 1e9 + 1)
            volume = fat32.Volume(img)
            written = volume.read("/KORG/blechtribe/Plugin/" + OUT_NAME)
            volume.close()
            print("FSTEST.OUT on the card equals what was sent:", written == outcome["pattern"])
            if written != outcome["pattern"] or outcome["failures"]:
                raise SystemExit(1)
        return
    if not (a.read or a.write or a.dry_run):
        p.error("one of --emu, --dry-run, --read, --write, --make-input, --check-out")
    outcome = run(Device(mido_ask()), mode, input_bytes(), a.dry_run)
    if outcome and outcome["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
