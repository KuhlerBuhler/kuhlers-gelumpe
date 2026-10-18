# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the splash editor patch (docs/ideen.md idea 35,
tools/patch/splash_editor.py, docs/messungen/2026-10-10-startbild-editor.md).

`boot_cases` are what check.py runs on every patched copy that carries the
start hook: the stored image is drawn only when it is valid, and EXIT held at
power-on keeps all of the patch out. `editor_run` drives the device through
the new page and the editor like a user would and reports what it saw.

    tools/emu/.venv/bin/python tools/emu/splash_cases.py cases --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin]
    tools/emu/.venv/bin/python tools/emu/splash_cases.py run   --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin] [--png-dir DIR]
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))

import bootcache  # noqa: E402
import splash_editor as spec  # noqa: E402
import synthaddr  # noqa: E402
from machine import FIRMWARE_AT, FLASH_SIZE, STOCK_BOOT_LIMIT_S, Machine, blank_flash, load_flash  # noqa: E402

PAYLOAD_SIZE = 0x200000
from sdcard import MemoryMedium, SDCard  # noqa: E402

HEADER = 0x100
IMAGE = 0xC0000000
SPLASH = 0xC00F9854                 # image 13 in the VSB
START_HOOK = spec.START_CALL
DESC13 = 0xC00C5A54
PAGE_BYTE = 0xC0691328              # last Global page, must never become 20
SCREENS = 0xC03404C0
TICK = 0xC006F178                   # tick of the screen manager, widgets are drawn from here
SWITCH_SCREEN = 0xC0083D28          # (number, 0)
TRAP = 0xC01FF000                   # return address for calls, inside the free run and never executed
KEYS = {"menu": 0x09, "edit_prev": 0x08, "edit_next": 0x0C, "exit": 0x0D, "write": 0x0E, "sequencer": 0x15, "pattern_set": 0x1B}
KILL = spec.KILL_SWITCH


# ---- images and records ------------------------------------------------------------
def display_of(image):
    """The 1024 bytes of an image as the display holds them: bit 7 is the top row of a page there, bit 0 here."""
    out = bytearray(1024)
    for page in range(8):
        for x in range(128):
            b = image[page * 128 + x]
            out[page * 128 + x] = sum(1 << k for k in range(8) if b & (0x80 >> k))
    return bytes(out)


def record_of(image, ident=spec.RECORD_ID, version=spec.RECORD_VERSION, length=None):
    head = struct.pack("<IHH", ident, version, len(image) if length is None else length) + bytes(image)
    return head + struct.pack("<I", zlib.crc32(head) & 0xFFFFFFFF)


def record_valid(raw):
    return (len(raw) == spec.RECORD_SIZE and struct.unpack_from("<IHH", raw)[0] == spec.RECORD_ID
            and zlib.crc32(raw[:-4]) & 0xFFFFFFFF == struct.unpack_from("<I", raw, spec.RECORD_SIZE - 4)[0])


def vsb_image(payload):
    return bytes(payload[SPLASH - IMAGE:SPLASH - IMAGE + spec.IMAGE_BYTES])


def other_image(payload):
    """A start image that differs from the VSB's everywhere."""
    return bytes(b ^ 0xFF for b in vsb_image(payload))


def has_start_hook(payload):
    """True when the call after the rescue paths goes into the splash editor's start code."""
    word = struct.unpack_from("<I", payload, START_HOOK - IMAGE)[0]
    if word >> 24 != 0xEB:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.START_AT <= START_HOOK + 8 + (off << 2) < spec.START_END


# ---- a device to drive -----------------------------------------------------------------
def user_flash(machine):
    """The flash without the region that holds the firmware image (machine.py writes the running image there): what the device keeps
    for the user. Two copies of a patch that differ in the image still compare equal here when they saved the same."""
    mem = machine.flash.mem
    return bytes(mem[:FIRMWARE_AT]) + bytes(PAYLOAD_SIZE) + bytes(mem[FIRMWARE_AT + PAYLOAD_SIZE:])


class Dev:
    def __init__(self, payload, flash=None, held=0, machine=None):
        self.m = machine or Machine(bytes(payload), flash)
        self.m.held = held
        self.synth = self.m.profile.build == "synth"

    def a(self, addr):
        """A firmware place of the Sampler as this build has it: the synth's entry in data/synth-map/, else the address itself
        (an address read out of the running firmware, the patch's own areas, and every place of the Sampler's builds)."""
        return synthaddr.table().get(addr, addr) if self.synth else addr

    def run(self, seconds):
        self.m.finish_boot()          # Korg's own build first loads its user data; a no-op once the main screen is up
        self.m.run_until(self.m.time_ns / 1e9 + seconds)

    def u32(self, addr):
        return struct.unpack("<I", bytes(self.m.uc.mem_read(self.a(addr), 4)))[0]

    def read(self, addr, n):
        return bytes(self.m.uc.mem_read(self.a(addr), n))

    def press(self, key, wait=0.3):
        self.m.press(KEYS[key] if isinstance(key, str) else key, True)
        self.run(0.05)
        self.m.press(KEYS[key] if isinstance(key, str) else key, False)
        self.run(wait)

    def turn(self, delta, wait=0.3):
        self.m.send([0x01, 0x00, 0x00, delta & 0xFF, 0])
        self.run(wait)

    def call(self, func, *args, at=TICK):
        """Run a firmware function once, from inside the screen manager's tick (a safe place for UI code)."""
        import unicorn
        m, uc, arm = self.m, self.m.uc, self.m.A
        func, at = self.a(func), self.a(at)
        hit = []
        hook = uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: (hit.append(1), u.emu_stop()), begin=at, end=at)
        uc.ctl_flush_tb()          # code already translated would not call the new hook
        end = m.time_ns / 1e9 + 2.0
        while not hit and m.time_ns / 1e9 < end:
            m.run_slice()
            if not hit:
                m.lines()
                m.irq()
        uc.hook_del(hook)
        uc.ctl_flush_tb()
        if not hit:
            raise RuntimeError("the screen tick did not come")
        regs = [arm.UC_ARM_REG_R0 + i for i in range(13)] + [arm.UC_ARM_REG_SP, arm.UC_ARM_REG_LR, arm.UC_ARM_REG_PC, arm.UC_ARM_REG_CPSR]
        saved = [uc.reg_read(r) for r in regs]
        for i, value in enumerate(args):
            uc.reg_write(arm.UC_ARM_REG_R0 + i, value & 0xFFFFFFFF)
        uc.reg_write(arm.UC_ARM_REG_SP, (saved[13] - 0x400) & ~7)
        uc.reg_write(arm.UC_ARM_REG_LR, TRAP)
        uc.reg_write(arm.UC_ARM_REG_PC, func)
        end = m.time_ns + 2_000_000_000
        uc.ctl_set_exits([TRAP, *m.ENTRIES])
        try:
            while uc.reg_read(arm.UC_ARM_REG_PC) != TRAP and m.time_ns < end and not m.asserts:
                m.run_slice(limit=end)
                if uc.reg_read(arm.UC_ARM_REG_PC) != TRAP:
                    m.lines()
                    m.irq()
        finally:
            uc.ctl_set_exits(list(m.ENTRIES))
        result = uc.reg_read(arm.UC_ARM_REG_R0)
        returned = uc.reg_read(arm.UC_ARM_REG_PC) == TRAP
        for r, value in zip(regs, saved):
            uc.reg_write(r, value)
        if not returned:
            raise RuntimeError(f"{func:#x} did not return")
        return result

    def fb(self):
        return bytes(b for row in self.m.fb for b in row)

    def px(self, x, y):
        return (self.fb()[(y // 8) * 128 + x] >> (y % 8)) & 1

    def screen(self):
        mgr = self.u32(SCREENS)
        cur = self.u32(mgr + 0x20) if mgr else 0
        return {"number": self.u32(mgr + 0x2C) if mgr else None, "page": self.u32(cur + 0x2C) if cur else None,
                "window": self.u32(mgr + 0x24) if mgr else None}

    def state(self):
        keys = ("magic", "mode", "cursor", "phase", "tick", "redraw", "pushed")
        return dict(zip(keys, (self.u32(spec.STATE + 4 * i) for i in range(len(keys)))))

    def ascii(self, rows=range(64), cols=range(128)):
        fb = self.fb()
        return "\n".join("".join("#" if (fb[(y // 8) * 128 + x] >> (y % 8)) & 1 else "." for x in cols) for y in rows)

    def png(self, path):
        self.m.png(path)


def flash_with(flash, patches):
    """A flash image (the user's, or a blank one) with byte strings written at addresses."""
    mem = bytearray(flash) if flash else blank_flash()
    for at, data in patches:
        mem[at:at + len(data)] = data
    return bytes(mem)


# ---- the boot cases check.py runs --------------------------------------------------------
SAMPLE = 0.01          # seconds of device time between two looks at the display during the start image
MIN_FRAMES = 5         # looks the start image has to be on screen for, or it did not stay long enough to be seen


def boot_case(payload, flash, held=0, limit=2.0):
    """Boot once. Every display frame from the first drawn pixel until the display goes blank again (the time
    the start image is up), whether the main screen came, the state.

    How long the start image stays depends on what the firmware does at start, which depends on the flash
    (a used flash takes a few ms longer than an erased one). So no probe time is fixed; the window is found."""
    vsb, mine = display_of(vsb_image(payload)), None
    dev = Dev(payload, flash, held)
    stock = dev.m.profile.build == "stock"
    limit = max(limit, STOCK_BOOT_LIMIT_S) if stock else limit
    shown = []
    sector = bytes(dev.m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + 0x1000])
    t = 0.0
    while t < limit and not dev.m.asserts:
        t += SAMPLE
        dev.m.run_until(t)
        frame = dev.fb()
        if any(frame):
            shown.append(frame)
        elif shown:
            break
    while dev.m.time_ns < limit * 1e9 and not dev.m.asserts and dev.screen()["number"] != 1:
        dev.run(0.02)
    return {
        "frames": shown, "vsb": vsb, "screen_1": dev.screen()["number"] == 1, "asserts": dev.m.asserts,
        "magic": dev.u32(spec.STATE), "descriptor": dev.u32(DESC13), "dsp_uploads": list(dev.m.dsp_uploads), "stock": stock,
        "flash_untouched": bytes(dev.m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + 0x1000]) == sector,
        "dev": dev,
    }


def summary(seen):
    """The images seen in a row, e.g. ['vsb', 'vsb', 'other'] as 'vsb x2/other x1'."""
    runs = []
    for s in seen:
        if runs and runs[-1][0] == s:
            runs[-1][1] += 1
        else:
            runs.append([s, 1])
    return "/".join(f"{name} x{n}" for name, n in runs) or "nothing"


# Korg's own build draws its loading progress over the start image: it clears the two pixel rows 61 and 62 (bits 5 and 6
# of a byte, display bit 0 the top row) in page 7, columns 9 to 119 (docs/messungen/2026-10-14-stock-blech.md).
# Hacktribe's build draws nothing there.
PROGRESS_BAR = range(7 * 128 + 9, 7 * 128 + 120)
PROGRESS_MASK = 0x9F


def same_image(frame, image, bar=False):
    """Whether the frame is the image; with `bar`, the progress bar of Korg's own build may be drawn over it."""
    if frame == image:
        return True
    return bar and all(a == b or (i in PROGRESS_BAR and a == b & PROGRESS_MASK) for i, (a, b) in enumerate(zip(frame, image)) if a != b)


def classify(frame, images, bar=False):
    for name, image in images.items():
        if same_image(frame, image, bar):
            return name
    return "blank" if not any(frame) else "other"


def boot_case_specs(payload):
    """The images the display can show, and the eight storage cases: (name, what is written into the flash, held buttons, image it must show, armed)."""
    vsb = vsb_image(payload)
    mine = other_image(payload)
    images = {"vsb": display_of(vsb), "stored": display_of(mine)}
    good = record_of(mine)
    flipped = bytearray(good)
    flipped[8 + 100] ^= 1
    cases = [
        ("empty", [(spec.FLASH_RECORD, b"\xff" * spec.RECORD_SIZE)], 0, "vsb", True),
        ("valid", [(spec.FLASH_RECORD, good)], 0, "stored", True),
        ("bit_flipped", [(spec.FLASH_RECORD, bytes(flipped))], 0, "vsb", True),
        ("half_written", [(spec.FLASH_RECORD, b"\xff" * spec.RECORD_SIZE), (spec.FLASH_RECORD, good[:512])], 0, "vsb", True),
        ("exit_held", [(spec.FLASH_RECORD, good)], KILL, "vsb", False),
        # each of these has a CRC that fits, so only the header check can turn them away
        ("wrong_id", [(spec.FLASH_RECORD, record_of(mine, ident=spec.RECORD_ID ^ 1))], 0, "vsb", True),
        ("wrong_version", [(spec.FLASH_RECORD, record_of(mine, version=2))], 0, "vsb", True),
        ("wrong_length", [(spec.FLASH_RECORD, record_of(mine, length=512))], 0, "vsb", True),
    ]
    return images, good, cases


BOOT_CASES = 9      # the eight of boot_case_specs and the Global menu with EXIT held


def boot_case_entry(payload, flash, i):
    """Boot case i (0 to 8) as a check.py entry {id, ok, detail}. They boot on their own, so they can run side by side."""
    images, good, cases = boot_case_specs(payload)
    if i == len(cases):
        r = boot_case(payload, flash_with(flash, [(spec.FLASH_RECORD, good)]), KILL)
        return {"id": "splash:exit_held_menu", "ok": kill_switch_menu(r["dev"]),
                "detail": "with EXIT held the Global menu has its 20 original pages, no page 20, no editor"}
    name, patches, held, want, armed = cases[i]
    r = boot_case(payload, flash_with(flash, patches), held)
    seen = [classify(f, images, r["stock"]) for f in r["frames"]]       # Korg's own build draws its loading bar over the image
    # drawing the image takes about 12 ms, so a look every 10 ms can fall into it: the first one or two are the image half drawn
    for _ in range(2):
        if len(seen) > MIN_FRAMES and seen[0] == "other":
            seen.pop(0)
    ok = (len(seen) >= MIN_FRAMES and all(s == want for s in seen) and r["screen_1"] and not r["asserts"] and r["flash_untouched"]
          and (r["magic"] == spec.MAGIC) == armed and len(r["dsp_uploads"]) == 1)
    return {"id": f"splash:{name}", "ok": ok,
            "detail": f"start image {want} (seen {summary(seen)}), main screen {'reached' if r['screen_1'] else 'NOT reached'}, "
                      f"patch {'armed' if r['magic'] == spec.MAGIC else 'off'}, DSP booted {len(r['dsp_uploads'])} time(s)"
                      + ("" if not r["asserts"] else f", asserts {r['asserts']}")}


def boot_case_task(i):
    """boot_case_entry in a worker (parallel.py)."""
    import parallel
    return boot_case_entry(parallel.shared["payload"], parallel.shared["flash"], i)


def boot_cases(patched, flash=None):
    """The mandatory storage and kill switch cases as check.py entries [{id, ok, detail}]."""
    return [boot_case_entry(patched, flash, i) for i in range(BOOT_CASES)]


def go_to_global(dev):
    """From the main screen to Global: MENU, Edit right until the Global header (screen 8), MENU."""
    dev.run(0.5)
    dev.press("menu")
    for _ in range(60):
        if dev.screen()["number"] == 8:
            break
        dev.press("edit_next", 0.15)
    dev.press("menu", 0.4)
    return dev.screen()


def kill_switch_menu(dev):
    dev.run(3.5)
    if go_to_global(dev)["number"] != 9:
        return False
    pages = []
    for _ in range(21):
        dev.press("edit_next", 0.2)
        pages.append(dev.screen()["page"])
    dev.press("menu", 0.3)                     # MENU on page 0 does nothing, on 19 it opens XY calibration
    return (pages == list(range(1, 20)) + [0, 1] and dev.u32(spec.STATE) != spec.MAGIC and not dev.m.asserts
            and dev.u32(PAGE_BYTE) <= 19)


# ---- the scripted run -----------------------------------------------------------------------
def region_equal(a, b, rows):
    """Frames equal over display rows (pixel rows), whole columns."""
    ra = {(y // 8) for y in rows}
    return all(a[p * 128:(p + 1) * 128] == b[p * 128:(p + 1) * 128] for p in ra)


def editor_run(base, patched, flash=None, png_dir=None):
    """Navigation, the editor, WRITE, EXIT and a restart with the stored image. Returns {ok, steps}."""
    steps = []
    evidence = {}

    def step(name, ok, detail=""):
        steps.append({"step": name, "ok": bool(ok), "detail": detail})

    vsb = vsb_image(patched)
    flash_in = flash_with(flash, [(spec.FLASH_RECORD, b"\xff" * spec.RECORD_SIZE)])
    stock = Dev(base, flash_in, machine=bootcache.booted(bytes(base), flash_in, 0, 4.0)[0])
    dev = Dev(patched, flash_in, machine=bootcache.booted(bytes(patched), flash_in, 0, 4.0)[0])
    step("boot", dev.screen()["number"] == 1 and not dev.m.asserts and dev.u32(spec.STATE) == spec.MAGIC
         and len(dev.m.dsp_uploads) == len(stock.m.dsp_uploads) == 1,
         f"main screen, patch armed, DSP booted {len(dev.m.dsp_uploads)} time(s), stock {len(stock.m.dsp_uploads)}")
    step("start image is the VSB's with nothing stored", True, "see boot cases")

    # navigation to Global and through pages 0..19, against the unpatched firmware
    here, there = go_to_global(dev), go_to_global(stock)
    step("Global screen opens", here["number"] == 9 and there["number"] == 9 and here["page"] == 0, f"{here}")
    same, value_same, pages = True, True, []
    for page in range(20):
        a, b = dev.fb(), stock.fb()
        pages.append(page)
        # the header band (display rows 0 to 9, page counter n/20 against n/21) is the one thing that differs
        if not (dev.screen()["page"] == stock.screen()["page"] == page and region_equal(a, b, range(16, 64))):
            same = False
            step(f"page index {page} equals stock", False, f"page {dev.screen()['page']} / {stock.screen()['page']}")
        for delta in (1, -1):                    # VALUE has to act as before: the value row changes alike, and comes back
            dev.turn(delta, 0.2)
            stock.turn(delta, 0.2)
            if not region_equal(dev.fb(), stock.fb(), range(16, 64)):
                value_same = False
                step(f"VALUE {delta:+d} on index {page} equals stock", False)
        if page < 19:
            dev.press("edit_next", 0.25)
            stock.press("edit_next", 0.25)
    step("page indices 0 to 19 look as in the stock firmware, below the header", same)
    step("VALUE on indices 0 to 19 acts as in the stock firmware", value_same)
    dev.press("menu", 0.5)
    stock.press("menu", 0.5)
    step("MENU on XY CALIBRATION (index 19) still opens the calibration screen",
         dev.screen()["number"] == stock.screen()["number"] != 9 and region_equal(dev.fb(), stock.fb(), range(0, 64)),
         f"{dev.screen()['number']} / {stock.screen()['number']}")
    dev.press("exit", 0.5)
    stock.press("exit", 0.5)
    step("EXIT from there goes to the Global header (screen 8) as in the stock firmware",
         dev.screen()["number"] == stock.screen()["number"] == 8 and region_equal(dev.fb(), stock.fb(), range(0, 64)),
         f"{dev.screen()} / {stock.screen()}")
    dev.press("menu", 0.5)
    stock.press("menu", 0.5)
    step("MENU reopens the parameter pages on index 19", dev.screen()["number"] == stock.screen()["number"] == 9
         and dev.screen()["page"] == stock.screen()["page"] == 19 and region_equal(dev.fb(), stock.fb(), range(16, 64)),
         f"{dev.screen()} / {stock.screen()}")
    page19 = dev.fb()
    evidence["page19"] = dev.ascii()

    # page 20
    dev.press("edit_next", 0.4)
    s = dev.screen()
    page20 = dev.fb()
    evidence["page20"] = dev.ascii()
    step("Edit right on XY CALIBRATION (index 19) opens index 20, shown 21/21", s["number"] == 9 and s["page"] == spec.PAGE and dev.u32(PAGE_BYTE) == 19, f"{s}, page byte {dev.u32(PAGE_BYTE)}")
    title_rows = range(16, 30)
    step("title differs from XY CALIBRATION, the enter prompt below is the same",
         not region_equal(page19, page20, title_rows) and region_equal(page19, page20, range(33, 64)))
    widget = dev.read(dev.u32(dev.u32(dev.u32(SCREENS) + 0x20) + 0x24), 0x100)
    step("the title widget holds SPLASH SCREEN and the enter prompt", b"SPLASH SCREEN\0" in widget and b"[ Enter ]" in widget)
    dev.turn(1, 0.3)
    step("VALUE on index 20 does nothing", dev.fb() == page20 and dev.u32(PAGE_BYTE) == 19)
    dev.press("edit_prev", 0.4)
    step("Edit left on index 20 goes back to index 19", dev.screen()["page"] == 19 and dev.fb()[512:] == page19[512:])
    dev.press("edit_next", 0.4)
    dev.press("edit_next", 0.4)
    step("Edit right on index 20 wraps to index 0", dev.screen()["page"] == 0 and dev.u32(PAGE_BYTE) == 0)
    dev.press("edit_prev", 0.4)
    step("Edit left on index 0 goes to index 20", dev.screen()["page"] == spec.PAGE and dev.u32(PAGE_BYTE) == 19)

    # the editor
    st = dev.state()
    dev.press("menu", 0.3)
    editor_start = dev.fb()
    st = dev.state()
    step("MENU opens the editor", st["mode"] == 1 and st["cursor"] == 0, f"{st}")
    differing = [i for i in range(1024) if editor_start[i] != display_of(vsb)[i]]
    step("the display shows the start image", differing in ([], [0]), f"bytes that differ: {differing}")
    seen = set()
    for _ in range(24):
        dev.run(0.05)
        seen.add(dev.px(0, 0))
    step("pixel (0,0) blinks", seen == {0, 1}, f"values seen {sorted(seen)}")
    evidence["editor"] = dev.ascii(rows=range(0, 16), cols=range(0, 64))
    dev.turn(5, 0.3)
    step("VALUE moves the cursor", dev.state()["cursor"] == 5)
    differing = [i for i in range(1024) if dev.fb()[i] != display_of(dev.read(spec.EDIT, 1024))[i]]
    step("the image stays on the display after VALUE", differing in ([], [5]), f"bytes that differ: {differing}")
    # and nothing is drawn but the cursor in between: on the device the page showed for a tick before the image came back. The
    # emulator sends the display only after the tick, so what counts is what is written into the display buffer: no clearing of it
    # (0xC0015988 from 0xC003F5F4) and no drawing of text or images (0xC00158B4, returning to 0xC00158B8), only the cursor pixel
    import unicorn
    writes = {}
    def seen(u, acc, addr, sz, v, d):
        lr = u.reg_read(dev.m.A.UC_ARM_REG_LR)
        writes[lr] = writes.get(lr, 0) + 1
    hook = dev.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, seen, begin=dev.a(0xC031B310), end=dev.a(0xC031B310) + 1023)
    dev.turn(1, 0.4)
    dev.m.uc.hook_del(hook)
    pixels, cleared = writes.get(dev.a(0xC00158B8), 0), writes.get(dev.a(0xC003F5F4), 0)
    # the cursor alone is a few pixels: its old place, its new place, a blink
    step("the page is not drawn while the dial turns", cleared == 0 and pixels <= 8,
         f"display writes after a click by return address: { {hex(k): v for k, v in writes.items()} }")
    dev.turn(-1, 0.3)                        # back to pixel 5 for the steps below
    dev.turn(-6, 0.3)
    step("VALUE left of pixel 0 wraps to the last pixel", dev.state()["cursor"] == 8191)
    dev.turn(1, 0.3)
    dev.turn(127, 0.3)
    dev.turn(1, 0.3)
    step("at the end of a row the cursor goes into the next row", dev.state()["cursor"] == 128)
    dev.turn(-128, 0.3)
    dev.turn(3, 0.3)
    edit_before = dev.read(spec.EDIT, 1024)
    dev.press("menu", 0.3)
    edit_after = dev.read(spec.EDIT, 1024)
    changed = [i for i in range(1024) if edit_before[i] != edit_after[i]]
    step("MENU flips the pixel under the cursor", changed == [3] and edit_before[3] ^ edit_after[3] == 0x80, f"{changed}")
    dev.press("edit_next", 0.3)
    dev.press("edit_prev", 0.3)
    step("Edit left and right are ignored in the editor", dev.screen()["page"] == spec.PAGE and dev.state()["mode"] == 1)
    dev.press("menu", 0.3)
    step("MENU again flips it back", dev.read(spec.EDIT, 1024) == edit_before)
    # SHIFT held: the dial moves the cursor up and down (device 18.10.)
    dev.m.press(0x0A, True)
    dev.run(0.1)
    dev.turn(2, 0.3)
    down = dev.state()["cursor"]
    dev.turn(-3, 0.3)
    up = dev.state()["cursor"]
    dev.turn(1, 0.3)
    dev.m.press(0x0A, False)
    dev.run(0.1)
    step("SHIFT held, VALUE moves the cursor by rows and wraps", down == 3 + 256 and up == 8192 - 128 + 3 and dev.state()["cursor"] == 3
         and dev.read(spec.EDIT, 1024) == edit_before, f"two rows down {down}, three up {up}, one down {dev.state()['cursor']}")
    # MENU held: the pixel flips on the press, then every pixel the cursor passes gets that colour, none skipped on a fast turn
    dev.m.press(0x09, True)
    dev.run(0.2)
    dev.turn(4, 0.3)
    dev.m.press(0x09, False)
    dev.run(0.2)
    dev.turn(1, 0.3)
    painted = dev.read(spec.EDIT, 1024)
    colour = (painted[3] >> 7) & 1
    changed = [i for i in range(1024) if painted[i] != edit_before[i]]
    step("MENU held paints the colour of its flip along the cursor's way", colour != (edit_before[3] >> 7) & 1 and all((painted[i] >> 7) & 1 == colour for i in range(3, 8))
         and painted[8] == edit_before[8] and set(changed) <= set(range(3, 8)) and dev.state()["cursor"] == 8 and not dev.m.asserts,
         f"colour {colour}, bytes changed {changed}, cursor {dev.state()['cursor']}")
    shown = [i for i in range(1024) if i != 8 and dev.fb()[i] != display_of(painted)[i]]
    step("the painted pixels are on the display", shown == [], f"bytes that differ besides the cursor: {shown}")
    dev.m.uc.mem_write(spec.EDIT, bytes(edit_before))          # back to where the steps below start: the image as before, cursor on 3
    dev.m.uc.mem_write(spec.STATE + 8, (3).to_bytes(4, "little"))
    dev.press("menu", 0.3)
    wanted = bytes(edit_after)
    dev.press("write", 0.1)
    windows = []
    for _ in range(40):
        dev.run(0.1)
        windows.append(dev.screen()["window"])
    stored = bytes(dev.m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + spec.RECORD_SIZE])
    step("WRITE stores a record at 0x7F0000", record_valid(stored) and stored[8:8 + 1024] == wanted, f"{spec.FLASH_RECORD:#x}")
    # The firmware saves the Globals on every WRITE in this menu, as it does without our patch. On an erased flash
    # its first save also writes a mark ("ULEG", 8 bytes) at 0x7EF000: the unpatched firmware does the same on the
    # same WRITE, so a flash that already has it (a used one) does not show it.
    own, mark = f"{spec.FLASH_RECORD:#x}", 0x7EF000
    now = bytes(dev.m.flash.mem)
    # the emulator puts the booted firmware into its flash region at power on (docs/emulator.md); that is no WRITE of ours
    sectors = [x for x in changed_sectors(now, flash_in) if not FIRMWARE_AT <= int(x, 16) < FIRMWARE_AT + PAYLOAD_SIZE]
    fresh = flash_in[mark:mark + 0x1000] == b"\xff" * 0x1000
    mark_ok = f"{mark:#x}" not in sectors or (fresh and now[mark:mark + 0x1000] == b"ULEG" + bytes(4) + b"\xff" * (0x1000 - 8))
    step("only that 4 KiB sector and what the firmware's own WRITE changes (Globals 0x230000, on a fresh flash its mark at 0x7EF000) changed",
         own in sectors and set(sectors) <= {own, "0x230000", f"{mark:#x}"} and mark_ok, f"changed sectors {sectors}")
    after = dev.fb()
    exp = display_of(wanted)
    diff = [i for i in range(1024) if after[i] != exp[i]]
    step("the edited image is back on the display after the Working window", any(windows) and not windows[-1] and set(diff) <= {3}, f"window seen {any(windows)}, differing bytes {diff}")
    evidence["after_write"] = dev.ascii(rows=range(0, 16), cols=range(0, 64))

    # leave
    dev.press("exit", 0.6)
    step("EXIT leaves the editor to index 20", dev.state()["mode"] == 0 and dev.screen()["page"] == spec.PAGE and dev.screen()["number"] == 9)
    left = dev.fb()
    step("index 20 is drawn again as before", all(left[i] == page20[i] for i in range(1024) if not (84 <= i % 128 < 98 and i < 128)))
    evidence["page20_after_exit"] = dev.ascii()
    dev.press("exit", 0.6)
    step("EXIT on index 20 leaves the Global screen", dev.screen()["number"] == 8 and not dev.m.asserts)
    dev.press("menu", 0.5)
    step("Global opens on index 19 again, the page byte never held 20", dev.screen()["number"] == 9 and dev.screen()["page"] == 19 and dev.u32(PAGE_BYTE) == 19)
    dev.press("edit_next", 0.4)
    dev.press("menu", 0.4)
    step("the editor opens again", dev.state()["mode"] == 1)
    dev.press("sequencer", 0.3)
    step("other buttons do nothing in the editor, as in the stock Global screen", dev.state()["mode"] == 1 and dev.screen()["number"] == 9)
    dev.call(SWITCH_SCREEN, 1, 0)           # what the firmware does when something takes the screen away
    dev.run(0.6)
    step("a screen change from inside the editor resets it", dev.screen()["number"] == 1 and dev.state()["mode"] == 0 and dev.state()["pushed"] == 0 and not dev.m.asserts, f"{dev.screen()} {dev.state()}")
    go_to_global(dev)                       # opens on index 19, where the page byte stayed
    dev.press("edit_next", 0.4)
    dev.press("menu", 0.4)
    step("after that the editor still works", dev.state()["mode"] == 1 and dev.state()["cursor"] == 0 and not dev.m.asserts)

    # restart with the stored image
    flash_after = bytes(dev.m.flash.mem)
    again = boot_case(patched, flash_after)
    shown = [classify(f, {"stored": display_of(wanted), "vsb": display_of(vsb)}) for f in again["frames"]]
    step("after a restart the display shows the edited image", len(shown) >= MIN_FRAMES and all(s == "stored" for s in shown) and again["screen_1"] and not again["asserts"]
         and len(again["dsp_uploads"]) == 1, f"{summary(shown)}, DSP booted {len(again['dsp_uploads'])} time(s)")
    if png_dir:
        Path(png_dir).mkdir(parents=True, exist_ok=True)
        dev.png(Path(png_dir) / "editor.png")
    steps.extend(import_steps(patched, flash_in))
    return {"ok": all(s["ok"] for s in steps), "steps": steps, "evidence": evidence}


def bmp(pixels, width=128, top_down=False, ink=0, bpp=1, dib=40):
    """A Windows bitmap of `pixels` (rows of 0 and 1, 1 drawn) as image editors save it; `ink` is the palette index of black."""
    palette = [b"\0\0\0\0", b"\xff\xff\xff\0"][::1 if ink == 0 else -1]
    rows = []
    for y in range(64):
        row = bytearray(16)
        for x in range(min(width, 128)):
            if (ink if pixels[y][x] else 1 - ink):
                row[x >> 3] |= 0x80 >> (x & 7)
        rows.append(bytes(row))
    data = b"".join(rows if top_down else rows[::-1])
    off = 14 + dib + 8
    info = struct.pack("<IiiHHIIiiII", dib, width, -64 if top_down else 64, 1, bpp, 0, len(data), 2835, 2835, 2, 0) + bytes(dib - 40)
    return b"BM" + struct.pack("<IHHI", off + len(data), 0, 0, off) + info + b"".join(palette) + data


def image_of(pixels):
    """The 1024 bytes of the image format (byte (y/8) * 128 + x, bit 7 - y%8)."""
    out = bytearray(spec.IMAGE_BYTES)
    for y in range(64):
        for x in range(128):
            if pixels[y][x]:
                out[(y // 8) * 128 + x] |= 0x80 >> (y % 8)
    return bytes(out)


def import_steps(patched, flash):
    """KORG/blechtribe/splash.bmp through the import the BLECH menu calls: stored and shown from the next start, refused when it
    is no 128 x 64 BMP with 1 bit per pixel, reported when it is missing."""
    import fat32
    steps = []
    pic = [[1 if (x // 8 + y // 8) % 2 == 0 or x == y else 0 for x in range(128)] for y in range(64)]
    files = {"bottom-up": (bmp(pic), 0), "top-down, black as index 1": (bmp(pic, top_down=True, ink=1), 0),
             "header of 124 bytes": (bmp(pic, dib=124), 0), "100 pixels wide": (bmp(pic, width=100), 2),
             "4 bits per pixel": (bmp(pic, bpp=4), 2), "missing": (None, 1)}
    for name, (data, want) in files.items():
        img = bytearray(fat32.format_image(64 * 1024 * 1024))
        vol = fat32.open_volume(img)
        vol.mkdir("/KORG")
        vol.mkdir("/KORG/blechtribe")
        if data:
            vol.write("/KORG/blechtribe/splash.bmp", data)
        vol.close()
        dev = Dev(patched, flash)
        dev.m.insert_card(SDCard(MemoryMedium(img)))
        dev.run(4)
        got = dev.call(spec.IMPORT_ENTRY)
        stored = dev.read(spec.RECBUF + 8, spec.IMAGE_BYTES) == image_of(pic)
        steps.append({"step": f"import: {name} gives {want}", "ok": got == want and (want != 0 or stored) and not dev.m.asserts,
                      "detail": f"returned {got}, image {'as drawn' if stored else 'not stored'}"})
        if name == "bottom-up":
            again = boot_case(patched, bytes(dev.m.flash.mem))
            shown = [classify(f, {"stored": display_of(image_of(pic))}) for f in again["frames"]]
            steps.append({"step": "after a restart the display shows the imported image",
                          "ok": len(shown) >= MIN_FRAMES and all(x == "stored" for x in shown) and again["screen_1"] and not again["asserts"],
                          "detail": summary(shown)})
    return steps


def changed_sectors(after, before):
    return [f"{at:#x}" for at in range(0, len(before), 0x1000) if after[at:at + 0x1000] != before[at:at + 0x1000]]


def main():
    import lifetime
    lifetime.exit_with_parent()      # ends with the test run that started this, also when that is killed
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases", "run"))
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--png-dir", type=Path)
    a = p.parse_args()
    base, patched = a.base.read_bytes()[HEADER:], a.patched.read_bytes()[HEADER:]
    flash = load_flash(a.flash) if a.flash else None
    if a.what == "cases":
        def compute():
            import parallel
            checks = parallel.run_tasks([("splash_cases", "boot_case_task", (i,)) for i in range(BOOT_CASES)],
                                        {"payload": patched, "flash": flash})
            return {"ok": all(c["ok"] for c in checks), "checks": checks}
        result = bootcache.cached_result("splash_cases", ("cases", patched, flash or b""), compute)
    elif a.png_dir:         # writes pictures, so it always runs
        result = editor_run(base, patched, flash, a.png_dir)
    else:
        result = bootcache.cached_result("splash_run", (base, patched, flash or b""), lambda: editor_run(base, patched, flash))
    ok = result["ok"]
    print(json.dumps(result, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
