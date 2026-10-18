"""Collect what we need from a blue Electribe 2 (the synth) that runs BLECH, into one zip file to send us. Read only.

Over USB-MIDI it asks the device search and BLECH's INFO, reads the RAM 0xC0000000 to 0xC1000000 once and the whole flash
(0 to 0x1000000) twice with BLECH's READ and FLASH READ. Every block is checked against the CRC-32 the device sends with it,
the flash is written only when both passes agree. Nothing is written to the device, nothing is executed on it; BLECH has no
command for either over this way (tools/patch/blech_sysex.py). The flash holds the device's patterns and settings and Korg's
firmware: the zip is for us only and never goes into a repository.

On Windows:
    1. Python 3 from python.org (tick "Add python.exe to PATH" in the installer)
    2. in a terminal:  py -m pip install mido python-rtmidi
    3. Electribe on USB, switched on, on its main screen, BLECH on it (not with EXIT held at power-on)
    4. py blue_report.py
Leave the device alone while it runs (about 10 to 20 minutes): no pattern change, no WRITE.

    python3 blue_report.py [--out FOLDER] [--port NAME] [--ram-length 0x1000000] [--flash-length 0x1000000]
    python3 blue_report.py --emu SYNTH.VSB --ram-length 0x1000 --flash-length 0x2000     # inside the repository, against the emulator
"""
import argparse
import hashlib
import json
import platform
import struct
import sys
import time
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

RAM_START, FLASH_END = 0xC0000000, 0x1000000
INFO, READ, FLASH = 0x60, 0x61, 0x64
R_INFO, R_READ, R_FLASH = 0x68, 0x69, 0x6C
FLAG_FLASH = 8
STATUS = {0: "ok", 1: "bad crc", 2: "refused", 3: "out of range", 4: "flash function failed", 5: "readback differs"}
TRIES = 3


def enc(data):
    """Bytes to the Electribe's 7-bit SysEx form: a byte of high bits, then seven bytes."""
    out = []
    for i in range(0, len(data), 7):
        chunk = data[i:i + 7]
        out.append(sum(1 << j for j, b in enumerate(chunk) if b & 0x80))
        out += [b & 0x7F for b in chunk]
    return out


def dec(data):
    out = []
    for i in range(0, len(data), 8):
        msb = data[i]
        out += [b | (0x80 if msb >> j & 1 else 0) for j, b in enumerate(data[i + 1:i + 8])]
    return bytes(out)


def midi_ask(port=None):
    """(ask, port name) over the Electribe's USB-MIDI port: ask(message) sends one SysEx and returns the next SysEx that comes back."""
    try:
        import mido
    except ImportError:
        raise SystemExit("mido is missing: py -m pip install mido python-rtmidi") from None
    ins, outs = mido.get_input_names(), mido.get_output_names()
    print("MIDI inputs: ", ins)
    print("MIDI outputs:", outs)
    if port is None:
        both = [n for n in ins if n in outs or any(n.split()[0] in o for o in outs)]
        cands = [n for n in ins if "electribe" in n.lower()] or both
        sound = [n for n in cands if "sound" in n.lower()]
        cands = sound or cands
        if len(cands) != 1:
            for i, n in enumerate(ins):
                print(f"  {i}: {n}")
            pick = input("Which input is the Electribe? number: ").strip()
            port = ins[int(pick)]
        else:
            port = cands[0]
    out_name = port if port in outs else next((o for o in outs if o.split()[0] == port.split()[0] and "electribe" in o.lower()), None)
    if out_name is None:
        for i, n in enumerate(outs):
            print(f"  {i}: {n}")
        out_name = outs[int(input("Which output is the Electribe? number: ").strip())]
    inp, out = mido.open_input(port), mido.open_output(out_name)
    print(f"using input {port!r}, output {out_name!r}")

    def ask(message):
        for _ in inp.iter_pending():
            pass
        out.send(mido.Message("sysex", data=message[1:-1]))
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            for incoming in inp.iter_pending():
                if incoming.type == "sysex":
                    return [0xF0, *incoming.data, 0xF7]
            time.sleep(0.002)
        raise SystemExit("no answer from the device within 6 s; stopping (is BLECH on it, and EXIT not held at power-on?)")
    return ask, f"{port} / {out_name}"


def search(ask):
    r = ask([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])
    if len(r) < 13 or r[1:4] != [0x42, 0x50, 0x01]:
        raise SystemExit(f"no Electribe answered the device search: {bytes(r).hex()}")
    return {"channel": r[4] & 0x0F, "model": r[6], "reply": bytes(r).hex(), "version": f"{r[10]}.{r[11]:02d}" if len(r) > 11 else None}


def talk(ask, dev, func, words=b""):
    ch, model = dev["channel"], dev["model"]
    r = ask([0xF0, 0x42, 0x30 + ch, 0x00, 0x01, model, func, *enc(words), 0xF7])
    if r[:6] != [0xF0, 0x42, 0x30 + ch, 0x00, 0x01, model]:
        raise SystemExit(f"an answer that is not for this device: {bytes(r[:12]).hex()}")
    return r[6], dec(r[7:-1])


def info(ask, dev):
    func, body = talk(ask, dev, INFO)
    if func != R_INFO:
        raise SystemExit(f"INFO got function {func:#x}: this firmware has no BLECH SysEx (or EXIT was held at power-on)")
    status, version, flags, block, table_crc, flash_block = struct.unpack_from("<6I", body)
    return {"status": status, "version": version, "flags": flags, "block": block, "table_crc": f"{table_crc:#010x}", "flash_block": flash_block}


def read_blocks(ask, dev, func, reply, start, length, block, label, limit):
    if not (limit[0] <= start and start + length <= limit[1]):
        raise SystemExit(f"refusing {label} at {start:#x}+{length:#x}: outside {limit[0]:#x}..{limit[1]:#x}")
    out, t0, step = bytearray(), time.monotonic(), max(length // 20, block)
    for addr in range(start, start + length, block):
        n = min(block, start + length - addr)
        for attempt in range(TRIES):
            f, body = talk(ask, dev, func, struct.pack("<II", addr, n))
            status, a, got, crc = struct.unpack_from("<4I", body)
            data = body[16:]
            if f != reply or a != addr or got != n:
                raise SystemExit(f"{label}: unexpected answer at {addr:#x}: function {f:#x}, address {a:#x}, length {got}")
            if status:
                raise SystemExit(f"{label} at {addr:#x}+{n}: {STATUS.get(status, status)}; stopping")
            if len(data) == n and zlib.crc32(data) == crc:
                break
            print(f"  {label} {addr:#x}: CRC does not match, asking again ({attempt + 1} of {TRIES})", flush=True)
        else:
            raise SystemExit(f"{label} {addr:#x}: the CRC did not match {TRIES} times; stopping")
        out += data
        if len(out) % step < block:
            print(f"  {label}: {len(out) * 100 // length:3d} %  ({time.monotonic() - t0:.0f} s)", flush=True)
    seconds = time.monotonic() - t0
    print(f"  {label}: {len(out)} bytes in {seconds:.1f} s, sha256 {hashlib.sha256(out).hexdigest()[:16]}")
    return bytes(out), seconds


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=None, help="folder for the zip (default: next to this script)")
    p.add_argument("--port", default=None, help="MIDI input name, when several could be the Electribe")
    p.add_argument("--ram-length", type=lambda x: int(x, 0), default=0x1000000)
    p.add_argument("--flash-length", type=lambda x: int(x, 0), default=FLASH_END)
    p.add_argument("--emu", metavar="VSB", help="against the local emulator (inside the repository only)")
    a = p.parse_args()
    if not 0 < a.flash_length <= FLASH_END or not 0 < a.ram_length <= 0x1000000:
        raise SystemExit("the lengths have to be above 0 and at most 0x1000000")
    if a.emu:
        sys.path.insert(0, str(Path(__file__).parent))
        from led_show import emulator_ask
        ask, _ = emulator_ask(a.emu)
        port = "emulator"
    else:
        ask, port = midi_ask(a.port)
    report = {"tool": "blue_report.py", "time": datetime.now().isoformat(timespec="seconds"), "host": platform.platform(),
              "python": sys.version.split()[0], "port": port}
    dev = search(ask)
    report["device"] = dev
    print(f"device: model byte {dev['model']:#04x} (0x23 the blue Electribe 2, 0x24 the Sampler), channel {dev['channel'] + 1}, version {dev['version']}")
    report["blech_info"] = inf = info(ask, dev)
    print(f"BLECH INFO: {inf}")
    if inf["status"] or not inf["block"]:
        raise SystemExit("BLECH INFO says no reads; stopping")
    block = min(inf["block"], 4096) if a.emu else inf["block"]      # the emulator's line is DIN: larger answers do not come back in time
    ram, ram_s = read_blocks(ask, dev, READ, R_READ, RAM_START, a.ram_length, block, "RAM", (RAM_START, RAM_START + 0x8000000))
    report["ram"] = {"start": f"{RAM_START:#x}", "length": len(ram), "seconds": round(ram_s, 1), "sha256": hashlib.sha256(ram).hexdigest()}
    flash = None
    if inf["flags"] & FLAG_FLASH and inf["flash_block"]:
        first, s1 = read_blocks(ask, dev, FLASH, R_FLASH, 0, a.flash_length, inf["flash_block"], "flash pass 1", (0, FLASH_END))
        second, s2 = read_blocks(ask, dev, FLASH, R_FLASH, 0, a.flash_length, inf["flash_block"], "flash pass 2", (0, FLASH_END))
        same = first == second
        report["flash"] = {"length": len(first), "seconds": [round(s1, 1), round(s2, 1)], "passes_agree": same,
                           "sha256": hashlib.sha256(first).hexdigest()}
        if same:
            flash = first
        else:
            diff = [hex(i) for i in range(0, len(first), inf["flash_block"]) if first[i:i + inf["flash_block"]] != second[i:i + inf["flash_block"]]]
            report["flash"]["differing_blocks"] = diff[:64]
            print(f"the two flash passes differ in {len(diff)} block(s): the flash is left out, the rest is kept")
    else:
        report["flash"] = {"skipped": "this BLECH has no FLASH READ"}
    folder = (a.out or Path(__file__).resolve().parent).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    name = folder / f"blechtribe-blau-{datetime.now():%Y%m%d-%H%M}.zip"
    with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("report.json", json.dumps(report, indent=1))
        z.writestr("ram-c0000000.bin", ram)
        if flash is not None:
            z.writestr("flash.bin", flash)
    print(f"\ndone: {name} ({name.stat().st_size >> 10} KiB). Please send us this file. It holds your patterns and settings, we keep it private.")


if __name__ == "__main__":
    sys.exit(main())
