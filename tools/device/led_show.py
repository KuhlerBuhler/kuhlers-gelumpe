"""Light Electribe LEDs through the firmware's own LED function.

RAM only: a 60-byte stub goes to 0xC1000000 (the Hacktribe upload area), runs
once through Hacktribe's execute command 0x57, and the original bytes are put
back afterwards. Stops before anything is written if the firmware code it
calls does not match the measured build.

    python3 led_show.py --emu VSB          # against the local emulator
    python3 led_show.py --dry-run          # on the laptop: checks only, writes nothing
    python3 led_show.py                     # on the laptop: the pads pattern, held
    python3 led_show.py --animate comet     # on the laptop: a running light over the pads
"""
import argparse
import hashlib
import struct
import sys
import time
from pathlib import Path

STUB_AT = 0xC1000000
PANEL_PTR = 0xC033E6FC
SET_LED = 0xC0028600
ICACHE_INVALIDATE = 0xC00016A4          # mcr c7,c5,0 then I bit on, returns via lr

EXPECTED = {                            # sha256 of the code the run relies on (own VSB)
    (0xC0028600, 0x40): "b55972bcd5fa7fd8fa20721b736998168998185272572be78a5a653ab4fb2bbc",
    (0xC00285C0, 0x40): "0bb1485cc873924be3b587a7cd1527d75e4f5ee0088ecd06ac872fd39f3f8dd8",
    (0xC00016A4, 0x34): "f33f00d1ca5392c857af29991ed0e4e10340bb4675df9e2f030af0caf730bd6a",
    (0xC0170624, 0x150): "144570d780ef267e8f41214147e8d02e25e25e242387748b389dea77d137dfeb",
    (0xC0024BF4, 0x100): "4e5fecab595459f0f631c6c2645f77964b01574b07d5170d3cef91295fead4d8",
}

# The 16 pads carry two LEDs each, red (0x2c + 2n) and blue (0x2d + 2n), so a
# pad is red, blue or both (purple), never green. Only four LEDs are true RGB,
# the bottom lights named LED_RGB_0..3 in the firmware, each with a red, green
# and blue element.
RGB = {0: (0x52, 0x53, 0x54), 1: (0x55, 0x56, 0x57), 2: (0x4c, 0x4d, 0x4e), 3: (0x4f, 0x50, 0x51)}


def rgb(index, red, green, blue):
    r, g, b = RGB[index]
    return [(r, red), (g, green), (b, blue)]


PATTERNS = {
    # Pads alternating red and blue, plus PLAY, REC, STOP.
    "pads": [(0x09, 255), (0x12, 255), (0x13, 255)] +
            [(0x2c + 2 * n, 255 if n % 2 == 0 else 0) for n in range(16)] +
            [(0x2d + 2 * n, 255 if n % 2 else 0) for n in range(16)],
    # The four bottom RGB lights as red, green, blue, white, to show they do green.
    "rgb": rgb(0, 255, 0, 0) + rgb(1, 0, 255, 0) + rgb(2, 0, 0, 255) + rgb(3, 255, 255, 255),
    # Pads 1..6 red at falling brightness, to see whether the pad LEDs dim (PWM).
    "bright": [(0x2c + 2 * n, v) for n, v in enumerate([255, 192, 128, 64, 32, 12])],
}

PAD_RED = [0x2c + 2 * n for n in range(16)]
PAD_BLUE = [0x2d + 2 * n for n in range(16)]
PADS_OFF = [(i, 0) for i in PAD_RED + PAD_BLUE]


# Physical layout of the 16 pads: GRID[row][col] = pad index, 8 columns, 2 rows.
# Adjust this if the wave runs the wrong way or the checkerboard looks off.
GRID = [[0, 1, 2, 3, 4, 5, 6, 7], [8, 9, 10, 11, 12, 13, 14, 15]]
# A pad's colour as (red on, blue on); the wave steps each cell one place on.
COLOURS = {"purple": (1, 1), "blue": (0, 1), "red": (1, 0)}
CYCLE = ["purple", "blue", "red"]        # blue -> red, purple -> blue


def checker_frames(cols=8, rows=2, half=2, full=255):
    """A blue/purple checkerboard; a 5-wide brightness dip sweeps left to right,
    and each cell changes colour as the dark centre passes over it."""
    state = {(x, y): "blue" if (x + y) % 2 == 0 else "purple"
             for y in range(rows) for x in range(cols)}
    step = lambda c: CYCLE[(CYCLE.index(c) + 1) % 3]
    for _ in range(len(CYCLE)):           # one loop brings every cell back
        for centre in range(-half, cols + half + 1):
            frame = []
            for y in range(rows):
                for x in range(cols):
                    d = abs(x - centre)
                    bright = min(full, full * d // (half + 1))   # 0 at the centre, smooth over 5 pads
                    colour = step(state[(x, y)]) if centre >= x else state[(x, y)]
                    red, blue = COLOURS[colour]
                    frame += [(PAD_RED[GRID[y][x]], bright * red), (PAD_BLUE[GRID[y][x]], bright * blue)]
            yield frame
        state = {k: step(v) for k, v in state.items()}


def comet_frames():
    """A light running across the 16 pads and back: head red, tail blue."""
    for head in list(range(16)) + list(range(14, 0, -1)):
        yield [(PAD_RED[n], 255 if n == head else 0) for n in range(16)] + \
              [(PAD_BLUE[n], 255 if n == (head - 1) % 16 else 0) for n in range(16)]


ANIMATIONS = {"checker": checker_frames, "comet": comet_frames}


def stub(pairs):
    words = [0xE92D4070, 0xE59F4028, 0xE5944000, 0xE28F5028,   # push; r4 = *PANEL_PTR; r5 = table
             0xE4D51001, 0xE35100FF, 0x0A000004, 0xE4D52001,   # loop: idx, end?, value
             0xE1A00004, 0xE59FC00C, 0xE12FFF3C, 0xEAFFFFF7,   # set_led(panel, idx, value)
             0xE8BD8070, PANEL_PTR, SET_LED]
    return b"".join(struct.pack("<I", w) for w in words) + bytes(b for p in pairs for b in p) + b"\xff"


def enc(data):
    out = []
    for i in range(0, len(data), 7):
        block = data[i:i + 7]
        out.append(sum(((v >> 7) & 1) << k for k, v in enumerate(block)))
        out.extend(v & 127 for v in block)
    return out


def dec(data):
    out = bytearray()
    for i in range(0, len(data), 8):
        block = data[i:i + 8]
        out.extend(v | (((block[0] >> k) & 1) << 7) for k, v in enumerate(block[1:]))
    return bytes(out)


class Device:
    def __init__(self, ask):
        self.ask = ask
        reply = ask([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])
        if reply[:4] != [0xF0, 0x42, 0x50, 0x01] or reply[6] != 0x24:
            raise SystemExit(f"no Electribe sampler answered the search: {bytes(reply).hex()}")
        self.head = [0x42, 0x30 + reply[4], 0x00, 0x01, 0x24]

    def msg(self, func, payload=b""):
        return [0xF0, *self.head, func, *enc(payload), 0xF7]

    def read(self, addr, length):
        reply = self.ask(self.msg(0x52, struct.pack("<II", addr, length)))
        if reply[:7] != [0xF0, *self.head, 0x54]:
            raise SystemExit(f"read {addr:#x}: unexpected reply {bytes(reply[:12]).hex()}")
        data = dec(reply[9:-1])
        if len(data) != length:
            raise SystemExit(f"read {addr:#x}: {len(data)} bytes instead of {length}")
        return data

    def acked(self, func, payload, what):
        reply = self.ask(self.msg(func, payload))
        if reply != [0xF0, *self.head, 0x21, 0xF7]:
            raise SystemExit(f"{what}: no write ack, got {bytes(reply).hex()}")

    def write(self, addr, data, verify=True):
        self.acked(0x53, struct.pack("<II", addr, len(data)), f"address {addr:#x}")
        self.acked(0x54, data, f"data {addr:#x}")
        if verify and self.read(addr, len(data)) != data:
            raise SystemExit(f"write {addr:#x}: read back differs")

    def execute(self, addr):
        self.acked(0x57, struct.pack("<II", addr, 0), f"execute {addr:#x}")


# Only about a dozen LED messages survive one execute before the panel line
# drops the rest, so a frame goes out in small chunks; the SysEx round-trip
# between chunks gives the line time to send what it already has.
CHUNK = 8


def show_frame(dev, pairs):
    for i in range(0, len(pairs), CHUNK):
        dev.write(STUB_AT, stub(pairs[i:i + CHUNK]), verify=False)
        dev.execute(STUB_AT)


def run(dev, dry, frames, seconds=0.0):
    for (addr, length), digest in EXPECTED.items():
        if hashlib.sha256(dev.read(addr, length)).hexdigest() != digest:
            raise SystemExit(f"code at {addr:#x} differs from the measured build; nothing written")
    panel = struct.unpack("<I", dev.read(PANEL_PTR, 4))[0]
    if not 0xC0000000 <= panel < 0xC4000000 or dev.read(panel + 4, 1) != b"\0":
        raise SystemExit(f"panel object {panel:#x} not ready; nothing written")
    original = dev.read(STUB_AT, len(stub([(0, 0)] * CHUNK)))
    print(f"checks passed: firmware code matches, panel {panel:#x}, {len(frames)} frame(s)")
    if dry:
        print("dry run: nothing written")
        return
    try:
        # The stub code is identical every frame and only its data table changes,
        # so the instruction cache is flushed once up front.
        dev.execute(ICACHE_INVALIDATE)
        shown, state, deadline = 0, {}, time.monotonic() + seconds
        while True:
            frame = frames[shown % len(frames)]
            changed = [(i, v) for i, v in frame if state.get(i) != v]
            show_frame(dev, changed)               # only what moved since the last frame
            state.update(frame)
            shown += 1
            if seconds <= 0 or time.monotonic() >= deadline:
                break
            time.sleep(0.03)
        if seconds > 0:
            show_frame(dev, PADS_OFF)              # leave the pads dark after an animation
        print(f"ran, {shown} frame(s) shown")
    finally:
        time.sleep(0.2)
        dev.write(STUB_AT, original)
        print("original bytes at the stub address restored")


def emulator_ask(vsb):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "emu"))
    from machine import Machine, UART1
    m = Machine(open(vsb, "rb").read()[0x100:], None)
    m.run_until(3.0)
    tx = m.uart[UART1]["tx"]

    def ask(message):
        start = len(tx)
        m.receive(UART1, message)
        deadline = m.time_ns + 2_000_000_000
        while m.time_ns < deadline:
            m.run_until(m.time_ns / 1e9 + 0.01)
            out = [b for b in tx[start:] if b < 0xF8]
            if out and out[-1] == 0xF7 and 0xF0 in out:
                return out[out.index(0xF0):]
            if m.asserts:
                raise SystemExit(f"emulator: firmware assertion {m.asserts[0]}")
        raise SystemExit("emulator: no answer")
    return ask, m


def mido_ask():
    import mido
    names = [n for n in mido.get_input_names() if "electribe" in n.lower() and "SOUND" in n]
    if len(names) != 1 or names[0] not in mido.get_output_names():
        raise SystemExit(f"expected exactly one Electribe SOUND port, found {names}")
    inp, out = mido.open_input(names[0]), mido.open_output(names[0])

    def ask(message):
        for _ in inp.iter_pending():
            pass
        out.send(mido.Message("sysex", data=message[1:-1]))
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            for incoming in inp.iter_pending():
                if incoming.type == "sysex":
                    return [0xF0, *incoming.data, 0xF7]
            time.sleep(0.005)
        raise SystemExit("no answer; stopping")
    return ask


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--emu", metavar="VSB")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pattern", choices=sorted(PATTERNS), default="pads")
    p.add_argument("--animate", choices=sorted(ANIMATIONS))
    p.add_argument("--seconds", type=float, default=6.0, help="how long an animation runs")
    a = p.parse_args()
    if a.animate:
        frames, seconds = list(ANIMATIONS[a.animate]()), a.seconds
    else:
        frames, seconds = [PATTERNS[a.pattern]], 0.0
    if a.emu:
        ask, m = emulator_ask(a.emu)
        run(Device(ask), a.dry_run, frames, seconds)
        m.run_until(m.time_ns / 1e9 + 1)
        print("emulator LEDs on:", {hex(k): v for k, v in sorted(m.leds.items()) if v}, "asserts:", m.asserts)
    else:
        run(Device(mido_ask()), a.dry_run, frames, seconds)


if __name__ == "__main__":
    main()
