"""Check on the own device that the screen state and display sit where the
emulator has them (docs/messungen/2026-10-09-menuezustand.md). Read only:
device search and RAM reads (0x52), nothing is written.

    python3 screen_check.py                 # on the laptop, device on USB
    python3 screen_check.py --emu VSB       # the same reads against the emulator
    python3 screen_check.py --watch 180     # print every change for three minutes
    python3 screen_check.py --held          # buttons held at the last power-on (2026-10-10-startphase.md)

Run it once on the main screen, once with MENU on MFX TYPE and once right
after turning IFX TYPE; the printout says what it read each time.
"""
import argparse
import struct
import time

from flash_dump import enc, dec, search
from led_show import emulator_ask, mido_ask

MANAGER_PTR = 0xC03404C0
EDIT_PTR = 0xC0348880
PATTERN_PTR = 0xC033E6A4
PANEL_PTR = 0xC033E6F8
DISPLAY = 0xC031B310
EXPECTED = {"manager": 0xC06C2210, "edit": 0xC06C41C0, "pattern": 0xC06B2798}
MODES = {1: "Hauptbildschirm", 3: "Menü Pattern", 7: "Menü Part", 8: "Menü Global", 10: "Menü Event",
         14: "Menü Data Util", 18: "Name eingeben", 19: "Menü Step", 21: "Menü Part Util", 37: "Menü Sample"}
PATTERN_PAGES = ["BPM", "SWING", "BEAT", "LENGTH", "PATTERN LEVEL", "MFX TYPE", "CLEAR MFX MOTION", "KEY",
                 "SCALE", "CHORD SET", "GATE ARP", "ALTERNATE 13-14", "ALTERNATE 15-16", "CHAIN TO", "CHAIN REPEAT"]


def reader(ask, channel):
    def read(addr, n):
        if not 0xC0000000 <= addr < 0xC8000000:
            raise SystemExit(f"refusing a read at 0x{addr:x}: outside RAM")
        body = list(addr.to_bytes(4, "little")) + list(n.to_bytes(4, "little"))
        r = ask([0xF0, 0x42, 0x30 + channel, 0, 1, 0x24, 0x52, *enc(body), 0xF7])
        if r[6] != 0x54:
            raise SystemExit(f"unexpected answer at 0x{addr:x}: {bytes(r[:10]).hex()}")
        return dec(r[9:-1])[:n]
    return read


def state(read, found):
    mgr = struct.unpack("<13I", read(found["manager"], 0x34))
    current, overlay, mode, kind = mgr[8], mgr[9], mgr[11], mgr[12]
    # The page counts only in the pattern and part menus; elsewhere the word is something else.
    page = struct.unpack("<I", read(current + 0x2C, 4))[0] if mode in (3, 7) and 0xC0000000 <= current < 0xC8000000 else None
    part = struct.unpack("<I", read(found["edit"] + 0x14, 4))[0] & 15
    pattern = found["pattern"] + 4
    mfx = read(pattern + 61, 1)[0]
    ifx = read(pattern + 0x800 + 33 + part * 0x330, 1)[0]
    name = PATTERN_PAGES[page] if mode == 3 and page is not None and page < len(PATTERN_PAGES) else ""
    where = f"Bildschirm {mode} ({MODES.get(mode, 'unbekannt')})" + (f", Seite {page} {name}".rstrip() if page is not None else "")
    return f"{where} | Fenster {'Art ' + str(kind) if overlay else 'keins'} | Part {part + 1} | Master {mfx + 1} | Insert {ifx + 1}"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--emu", metavar="VSB")
    p.add_argument("--watch", type=float, metavar="SECONDS", help="print every change of screen, page, window and part")
    p.add_argument("--held", action="store_true", help="print the buttons held at power-on and the start mode")
    a = p.parse_args()
    ask = emulator_ask(a.emu)[0] if a.emu else mido_ask()
    read = reader(ask, search(ask))
    u32 = lambda addr: struct.unpack("<I", read(addr, 4))[0]
    found = {"manager": u32(MANAGER_PTR), "edit": u32(EDIT_PTR), "pattern": u32(PATTERN_PTR)}
    for k, v in found.items():
        print(f"{k:8} 0x{v:08x} {'wie im Emulator' if v == EXPECTED[k] else f'ANDERS als im Emulator (0x{EXPECTED[k]:08x})'}")
    if a.held:
        raw = read(u32(PANEL_PTR) + 0x18, 0x0B)
        held = struct.unpack("<Q", raw[:8])[0]
        print(f"gehalten 0x{held:016x}, Startmodus {raw[8]}, SHIFT-Merker {raw[9]}, Panel-Update {raw[10]}")
        print("Bits:", [n for n in range(64) if held >> n & 1])
        return
    if a.watch:
        last, end = None, time.monotonic() + a.watch
        while time.monotonic() < end:
            line = state(read, found)
            if line != last:
                print(time.strftime("%H:%M:%S"), line, flush=True)
                last = line
            time.sleep(0.2)
        return
    print(state(read, found))
    img = read(DISPLAY, 1024)
    for y in range(0, 64, 2):
        print("".join("#" if (img[(y >> 3) * 128 + x] >> (y & 7)) & 1 else " " for x in range(0, 128)))


if __name__ == "__main__":
    main()
