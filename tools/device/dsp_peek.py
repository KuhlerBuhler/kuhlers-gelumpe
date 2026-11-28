"""Read DSP memory through the firmware's own host-port read (0xC00141F8, takes OS lock 1), run by BLECH EXEC.

    python3 dsp_peek.py --emu VSB [--steps ...]   # emulator with the DSP model
    python3 dsp_peek.py                           # device on USB
Prints JSON: per part the DSP words at switch, ramp, level, IFX ON, pan L/R, MFX SEND; the peak words.
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import remote_press as rp
from led_show import mido_ask
from remote_press import Blech

STUB_AT = 0xC1000000
PARAMS_AT = STUB_AT + 0x40
BUF_AT = STUB_AT + 0x80
BUF_MAX = 0x300
READ_FN = 0xC00141F8
CHECK = [(0xC00141F8, 0x90), (0xC0014AFC, 0x100), (0xC0000D80, 0x100), (0xC0000CA8, 0x80)]
STUB = [0xE92D4010, 0xE1A04000, 0xE5940000, 0xE5941004, 0xE1D420B8, 0xE1D430BA,
        0xE59FC004, 0xE12FFF3C, 0xE8BD8010, READ_FN]
PART_ON, STRIDE = 0x2C2, 0x6D
OFFS = {"on": 0, "ramp": 0x22, "level": 0x23, "ifx_on": 0x5C, "pan_l": 0x5F, "pan_r": 0x60, "mfx_send": 0x63}
PEAK = 0xFF9030F4


def emu_ask(vsb):
    sys.path.insert(0, str(Path(EMU)))
    from machine import Machine, UART1
    from dsp_model import DspModel
    from menu_cases import card_image
    from sdcard import MemoryMedium, SDCard
    m = Machine(open(vsb, "rb").read()[0x100:], None)
    model = DspModel.attach(m)
    m.insert_card(SDCard(MemoryMedium(card_image())))
    m.run_until(4.0)
    model.output(0.5, 0.25)
    tx = m.uart[UART1]["tx"]

    def ask(message):
        start = len(tx)
        m.receive(UART1, message)
        deadline = m.time_ns + 2_000_000_000
        while m.time_ns < deadline:
            m.run_until(m.time_ns / 1e9 + 0.01)
            out = [b for b in tx[start:] if b < 0xF8]
            if 0xF0 in out and 0xF7 in out[out.index(0xF0):]:
                b = out.index(0xF0)
                return out[b:out.index(0xF7, b) + 1]
            if m.asserts:
                raise SystemExit(f"emulator: assertion {m.asserts[0]}")
        raise SystemExit("emulator: no answer")
    return ask, m, model


def exec_arg(dev, addr, arg):
    func, body = dev.talk(0x6F, struct.pack("<II", addr, arg))
    status, _, value = struct.unpack_from("<3I", body)
    if func != 0x70 or status:
        raise SystemExit(f"EXEC refused: status {status}")
    return value


def dsp_read(dev, addr, words):
    assert 2 * words <= BUF_MAX
    dev.write(PARAMS_AT, struct.pack("<IIHH", addr, BUF_AT, words, 2))
    exec_arg(dev, STUB_AT, PARAMS_AT)
    raw = dev.read(BUF_AT, 2 * words)
    return list(struct.unpack(f"<{words}H", raw))


def snapshot(dev):
    out = {"parts": [], "peak": None}
    for p in range(16):
        base = PART_ON + STRIDE * p
        lo = dsp_read(dev, 0xFF800000 + 4 * base, 2 * 0x64)    # params +0 .. +0x63, 2 halves each
        word = lambda k: lo[2 * k] | lo[2 * k + 1] << 16
        out["parts"].append({n: hex(word(k)) for n, k in OFFS.items()})
    pk = dsp_read(dev, PEAK, 4)
    out["peak"] = [hex(pk[0] | pk[1] << 16), hex(pk[2] | pk[3] << 16)]
    return out


def model_snapshot(model):
    parts = []
    for p in range(16):
        base = PART_ON + STRIDE * p
        parts.append({n: (None if model.params.get(base + k) is None else hex(model.word(0xFF800000 + 4 * (base + k))))
                      for n, k in OFFS.items()})
    return parts


def main():
    global EMU
    ap = argparse.ArgumentParser()
    ap.add_argument("--emu")
    ap.add_argument("--emu-dir", default=str(HERE.parent / "emu"))
    ap.add_argument("--ref", help="VSB whose code bytes the device must match")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pad", action="store_true")
    a = ap.parse_args()
    EMU = a.emu_dir
    model = None
    if a.emu:
        ask, m, model = emu_ask(a.emu)
    else:
        ask = mido_ask()
    dev = Blech(ask)
    ref = open(a.ref or a.emu, "rb").read()[0x100:] if (a.ref or a.emu) else None
    for addr, n in CHECK:
        got = dev.read(addr, n)
        if ref is not None and got != ref[addr - 0xC0000000:addr - 0xC0000000 + n]:
            raise SystemExit(f"code at {addr:#x} differs from the reference; nothing written")
    print("code checks passed", file=sys.stderr)
    if a.dry_run:
        return 0
    original = dev.read(STUB_AT, BUF_AT - STUB_AT + BUF_MAX)
    try:
        dev.write(STUB_AT, b"".join(struct.pack("<I", w) for w in STUB))
        t0 = time.monotonic()
        if a.pad:
            wait = (lambda t: m.run_until(m.time_ns / 1e9 + t)) if a.emu else time.sleep
            snap = pad_run(dev, wait, model)
        else:
            snap = snapshot(dev)
        snap["seconds"] = round(time.monotonic() - t0, 2)
    finally:
        dev.write(STUB_AT, original)
        print("stub buffer restored", file=sys.stderr)
    if model is not None and not a.pad:
        snap["model"] = model_snapshot(model)
    if model is not None:
        snap["asserts"] = m.asserts
        snap["faults"] = model.faults[:5]
    print(json.dumps(snap, indent=1))
    return 0



# ---- pad comparison ---------------------------------------------------------
VOICE, VW, VOICES = 0x43AB, 0x1A, 24


def paddr(n):
    return (0xFF800000 if n < 0x4000 else 0xFF8F0000) + 4 * n


def read_params(dev, first, count):
    out = []
    while len(out) < count:
        n = min(count - len(out), BUF_MAX // 4)
        h = dsp_read(dev, paddr(first + len(out)), 2 * n)
        out += [h[2 * i] | h[2 * i + 1] << 16 for i in range(n)]
    return out


def voices(dev):
    words = read_params(dev, VOICE, VW * VOICES)
    return {v: [hex(w) for w in words[VW * v:VW * v + VW]] for v in range(VOICES) if words[VW * v]}


def part0(dev):
    w = read_params(dev, PART_ON, 0x64)
    return {n: hex(w[k]) for n, k in OFFS.items()}


def press(dev, step):
    mailbox, message_at, _, os_wait = rp.remote_of(dev)
    done = lambda: struct.unpack("<I", dev.read(mailbox + 8, 4))[0]
    for label, w, message in rp.command(step, rp.panel_names()):
        before = done()
        dev.write(STUB_AT, rp.message_stub(mailbox, message_at, message, os_wait) if message else rp.stub(mailbox, w, os_wait))
        ok = rp.Blech.execute(dev, STUB_AT) == 1 and (done() - before) & 0xFFFFFFFF == 1
        if not ok:
            raise SystemExit(f"{label} not run")
    dev.write(STUB_AT, b"".join(struct.pack("<I", w) for w in STUB))


def pad_run(dev, wait, model=None):
    out = {}
    out["before"] = {"part0": part0(dev), "voices": voices(dev)}
    press(dev, "pad1:down")
    wait(0.3)
    out["held"] = {"part0": part0(dev), "voices": voices(dev)}
    if model is not None:
        out["held"]["model"] = {v: model.voice(v) for v in model.voices()}
    press(dev, "pad1:up")
    wait(0.5)
    out["after"] = {"part0": part0(dev), "voices": voices(dev)}
    return out


if __name__ == "__main__":
    sys.exit(main())
