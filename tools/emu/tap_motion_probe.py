# SPDX-License-Identifier: GPL-2.0-only
"""Research probe for idea 39 (TAP plays a recorded knob motion), docs/messungen/2026-10-15-tap-motion.md.

Everything here runs on the firmware as it is, in the emulator, with two small ARM stubs that live in
RAM only (the free FF block of the image, never in a file). It does not touch tools/patch/script_*.s and
does not need the plugin runtime: the stubs use the same hook sites and the same way of calling
firmware functions as the runtime does (frame hook 0xC00836FC in the UiTask, input filter 0xC002837C
in the CsTask), so what they show carries over.

    E2_VSB=/path/SYSTEM.VSB E2_FLASH=/path/flash.bin \
        tools/emu/.venv/bin/python tools/emu/tap_motion_probe.py [--only knob,touch,motion,gate,bar,tap,runtime,cost]

Each check is printed with ok or FAIL and the numbers behind it; the exit status is 1 when one fails.
The numbers in the measurement file are from this script. The "runtime" section needs node (it compiles a
test plugin with tools/emu/tap_motion_request.mjs); the others need only Python with unicorn.
"""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import unicorn  # noqa: E402
from tools.patch.arm import assemble  # noqa: E402
from machine import Machine, load_flash  # noqa: E402
from splash_cases import Dev  # noqa: E402

# ---- firmware addresses (firmware 2.02 with Hacktribe) ----
FRAME_SITE = 0xC00836FC        # frame hook of the plugin runtime, UiTask, 25 Hz
INPUT_SITE = 0xC002837C        # panel message dispatcher, CsTask; the runtime's input filter sits here
KEY = 0xC0042BB8               # (key, down)
KNOB = 0xC0040A50              # (index, value)
TOUCH = 0xC004596C             # (x, y)
TEMPO_SET = 0xC004A80C         # (pattern object, tenths of a BPM, 1), what korg.tempo calls
PATTERN = 0xC033E6A4           # word that holds the pattern object (0xC06B2798 in this build)
TRANSPORT = 0xC06BC318
TEMPO = 0xC0691518
STEP = 0xC06904B0              # step counter, 0x48 per part
FRAME_LITERAL = 0xC031BB2C     # what the instruction at FRAME_SITE loads
CODE, STATE = 0xC01B0000, 0xC01B8000   # free FF block of the image, RAM only
TIMER3 = 0x01F0D010
EXIT_TRAP = 0xC01FF000         # return address for pure calls, never executed

# Offsets in the pattern object, measured for part 1 of the Init pattern on the main screen
KNOB_PARAM = {0: 0x81C, 1: 0x81D, 2: 0x828, 3: 0x812, 4: 0x813, 5: 0x816, 6: 0x818, 7: 0x826, 8: 0x819, 9: 0x80F, 10: 0x815}
PART_STRIDE = 0x330
MOTION_MODE = 0x807            # 0 Off, 1 Smooth, 2 Trigger Hold; a second copy sits 0x382E further
MOTION_COPY = 0x382E
BEAT, LENGTH = 0x2A, 0x29      # BEAT 0 16, 1 32, 2 8 Tri, 3 16 Tri; LENGTH bars minus one
MFX_XY = 0x40                  # flag (1 while touched), +2 x, +3 y in MASTER FX mode
MOTION_OUT = 0xC068DB1C        # what the motion engine plays for the first lane, 0xFFFFFFFF while silent

STUB = f"""
.equ S, {STATE:#x}
.equ PATTERN_OBJ, 0xC06B2798
.equ TIMER3, {TIMER3:#x}
; S + 0 enable, 4 last step, 8 armed, 12 playing, 16 position, 20 length, 24 lanes, 28 shift down,
;   32 plain TAPs taken, 36 bar shift, 40 SHIFT TAPs taken, 44 step at start, 48 injections,
;   52 slowest call (Timer3 ticks), 56 drop TAP, 60 inject during REC, 64 lanes from here: index word + 64 bytes
;   (255 is no entry), 68 bytes each
frame_stub:
    push {{r0-r12, lr}}
    ldr r4, =S
    ldr r0, [r4]
    cmp r0, #1
    bne fdone
    ldr r1, =0xC06BC318
    ldr r1, [r1]
    cmp r1, #1
    beq ftransport
    ldr r2, [r4, #60]
    cmp r2, #0
    beq fdone
    cmp r1, #4
    beq ftransport
    cmp r1, #5
    bne fdone
ftransport:
    ldr r1, =0xC06904B0
    ldr r5, [r1]
    ldr r6, [r4, #4]
    cmp r5, r6
    beq fdone
    str r5, [r4, #4]
    ldr r1, =PATTERN_OBJ
    ldrb r1, [r1, #0x2a]
    and r1, r1, #1
    add r1, r1, #4
    str r1, [r4, #36]
    ldr r0, [r4, #8]
    cmp r0, #0
    beq fplaying
    mov r2, r5, lsr r1
    mov r3, r6, lsr r1
    cmp r2, r3
    beq fplaying
    mov r0, #0
    str r0, [r4, #8]
    str r0, [r4, #16]
    str r5, [r4, #44]
    mov r0, #1
    str r0, [r4, #12]
fplaying:
    ldr r0, [r4, #12]
    cmp r0, #0
    beq fdone
    ldr r7, [r4, #16]
    ldr r0, [r4, #20]
    cmp r7, r0
    bhs fstop
    ldr r8, [r4, #24]
    add r9, r4, #64
floop:
    cmp r8, #0
    beq fadv
    ldr r0, [r9]
    add r2, r9, #4
    ldrb r1, [r2, r7]
    cmp r1, #255
    beq fnext
    ldr r10, =TIMER3
    ldr r10, [r10]
    ldr r12, =0xC0040A50
    blx r12
    ldr r11, =TIMER3
    ldr r11, [r11]
    sub r11, r11, r10
    ldr r0, [r4, #52]
    cmp r11, r0
    strhi r11, [r4, #52]
    ldr r0, [r4, #48]
    add r0, r0, #1
    str r0, [r4, #48]
fnext:
    add r9, r9, #68
    sub r8, r8, #1
    b floop
fadv:
    add r7, r7, #1
    str r7, [r4, #16]
    b fdone
fstop:
    mov r0, #0
    str r0, [r4, #12]
fdone:
    pop {{r0-r12, lr}}
    ldr r0, ={FRAME_LITERAL:#x}
    ldr pc, =0xC0083700
.pool

input_stub:
    push {{r0-r12, lr}}
    ldrb r1, [r0, #0x18]
    ldrb r2, [r0, #0x19]
    orrs r1, r1, r2
    bne ipass
    ldrb r1, [r0, #0x0c]
    cmp r1, #0
    bne ipass
    ldrb r2, [r0, #0x0d]
    ldrb r3, [r0, #0x0e]
    ldr r4, =S
    cmp r2, #10
    bne inotshift
    str r3, [r4, #28]
    b ipass
inotshift:
    cmp r2, #3
    bne ipass
    ldr r5, [r4, #56]
    cmp r5, #0
    beq ipass
    cmp r3, #0
    beq idrop
    ldr r5, [r4, #28]
    cmp r5, #0
    bne ishift
    ldr r5, [r4, #32]
    add r5, r5, #1
    str r5, [r4, #32]
    mov r5, #1
    str r5, [r4, #8]
    b idrop
ishift:
    ldr r5, [r4, #40]
    add r5, r5, #1
    str r5, [r4, #40]
idrop:
    pop {{r0-r12, lr}}
    bx lr
ipass:
    pop {{r0-r12, lr}}
    ldrb r3, [r0, #0x18]
    ldr pc, =0xC0028380
.pool

; r0 index, r1 value, r2 and r3 the last two arguments of the firmware's inner knob handler (r3 goes on the stack)
knob_inner:
    push {{r4, lr}}
    sub sp, sp, #8
    str r3, [sp]
    mov r3, r2
    mov r2, r1
    mov r1, r0
    ldr r0, =0xC03487EC
    ldr r0, [r0]
    ldr r12, =0xC00423A0
    blx r12
    add sp, sp, #8
    pop {{r4, pc}}
.pool
"""


class Lab:
    """One booted device and snapshots of it to branch from."""

    def __init__(self, vsb, flash):
        self.vsb = vsb
        self.payload = vsb[0x100:]
        self.flash = flash
        self.asm = assemble(STUB, origin=CODE)
        self.checks = []
        t = time.time()
        dev = Dev(self.payload, flash)
        dev.run(2)
        self.snap = dev.m.snapshot()
        self.pat = dev.u32(PATTERN)
        self.obj = dev.u32(0xC03487EC)
        self.boot_s = time.time() - t
        self.noise = self._noise()

    def fork(self, snap=None):
        m = Machine.from_snapshot(snap or self.snap, self.payload, self.flash)
        return Dev(self.payload, self.flash, machine=m)

    def _noise(self):
        x = self.fork()
        before = x.read(self.pat, 0x4900)
        x.run(0.3)
        after = x.read(self.pat, 0x4900)
        return {i for i in range(0x4900) if before[i] != after[i]}

    def check(self, name, ok, detail=None):
        self.checks.append(dict(id=name, ok=bool(ok), detail=detail))
        print(("ok   " if ok else "FAIL ") + name + ("  " + json.dumps(detail, default=str) if detail is not None else ""), flush=True)

    # ---- stubs ----------------------------------------------------------------------------
    def install(self, dev, lanes=(), length=16, drop_tap=False, record=False, frame=True):
        """The frame stub and the input stub into RAM, state block zeroed, lanes filled.
        `lanes` is a list of (knob index, list of values 0 to 254 or None per step)."""
        uc = dev.m.uc
        uc.mem_write(CODE, self.asm.sections[0][1])
        uc.mem_write(STATE, bytes(0x800))
        sym = self.asm.symbols
        for site, target in ((FRAME_SITE, "frame_stub"), (INPUT_SITE, "input_stub")):
            uc.mem_write(site, assemble(f"b {sym[target]}", origin=site).bytes)
        words = {20: length, 24: len(lanes), 56: int(drop_tap), 60: int(record)}
        for off, value in words.items():
            uc.mem_write(STATE + off, value.to_bytes(4, "little"))
        for i, (index, values) in enumerate(lanes):
            table = bytes(255 if v is None else v for v in (list(values) + [None] * 64)[:64])
            uc.mem_write(STATE + 64 + 68 * i, index.to_bytes(4, "little") + table)
        uc.mem_write(STATE + 4, dev.u32(STEP).to_bytes(4, "little"))
        uc.mem_write(STATE, (1 if frame else 0).to_bytes(4, "little"))
        uc.ctl_flush_tb()

    def state(self, dev, off):
        return dev.u32(STATE + off)

    def arm(self, dev):
        dev.m.uc.mem_write(STATE + 4, dev.u32(STEP).to_bytes(4, "little"))
        dev.m.uc.mem_write(STATE + 8, (1).to_bytes(4, "little"))

    def pure_call(self, dev, func, *args):
        """Instructions of one call of a firmware function made from the frame hook, with no interrupt and no
        task switch in between: what the call itself costs. Returns (instructions in the image, came back)."""
        m, uc, A = dev.m, dev.m.uc, dev.m.A
        regs = [A.UC_ARM_REG_R0 + i for i in range(13)] + [A.UC_ARM_REG_SP, A.UC_ARM_REG_LR, A.UC_ARM_REG_PC, A.UC_ARM_REG_CPSR]
        hit = []
        hook = uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: (hit.append(1), u.emu_stop()), begin=FRAME_SITE, end=FRAME_SITE)
        uc.ctl_flush_tb()
        end = m.time_ns / 1e9 + 2.0
        while not hit and m.time_ns / 1e9 < end:
            m.run_slice()
            if not hit:
                m.lines()
                m.irq()
        uc.hook_del(hook)
        saved = [uc.reg_read(r) for r in regs]
        for i, v in enumerate(args):
            uc.reg_write(A.UC_ARM_REG_R0 + i, v & 0xFFFFFFFF)
        uc.reg_write(A.UC_ARM_REG_SP, (saved[13] - 0x400) & ~7)
        uc.reg_write(A.UC_ARM_REG_LR, EXIT_TRAP)
        count = [0]
        counter = uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: count.__setitem__(0, count[0] + 1), begin=0xC0000000, end=0xC0FFFFFF)
        uc.ctl_flush_tb()
        uc.ctl_set_exits([EXIT_TRAP])
        uc.emu_start(func, EXIT_TRAP, count=3_000_000)
        back = uc.reg_read(A.UC_ARM_REG_PC) == EXIT_TRAP
        uc.hook_del(counter)
        uc.ctl_set_exits(list(m.ENTRIES))
        uc.ctl_flush_tb()
        for r, v in zip(regs, saved):
            uc.reg_write(r, v)
        return count[0], back

    # ---- helpers --------------------------------------------------------------------------
    def tap(self, dev, hold=0.05):
        dev.m.send([0, 3, 1, 0, 0])
        dev.run(hold)
        dev.m.send([0, 3, 0, 0, 0])

    def setpage(self, dev, page, turns):
        dev.press(0x09, 0.4)
        for _ in range(page - 1):
            dev.press(0x0C, 0.15)
        for t in turns:
            dev.m.send([1, 0, 0, t & 255, 0])
            dev.run(0.25)
        dev.press(0x0D, 0.4)

    def params(self, dev, size=0x4900):
        return dev.read(self.pat, size)

    def changed(self, before, after, limit=0x4900):
        return {i: (before[i], after[i]) for i in range(min(limit, len(before))) if before[i] != after[i] and i not in self.noise}

    def param(self, dev, knob=0, part=0):
        return dev.read(self.pat + KNOB_PARAM[knob] + PART_STRIDE * part, 1)[0]

    def tempo(self, dev):
        return dev.u32(TEMPO)

    def watch(self, dev, seconds, dt=0.005, knob=0):
        """(device ms, step counter, parameter byte) at every change of either, sampled every dt."""
        rows, last, t, t0 = [], None, 0.0, dev.m.time_ns
        while t < seconds:
            dev.run(dt)
            t += dt
            now = (dev.u32(STEP), self.param(dev, knob))
            if now != last:
                rows.append((round((dev.m.time_ns - t0) / 1e6), *now))
                last = now
        return rows


# ======================================================================================
def knob(lab):
    """1. A knob value from inside the firmware acts like a real knob turn."""
    print("\n== knob: UART panel message against a call of the firmware's knob handler from the frame hook ==")
    base = lab.fork()
    before_all = lab.params(base)
    mapping, equal, total = {}, 0, 0
    for index in sorted(KNOB_PARAM):
        for value in (0, 64, 128, 200, 255):
            outcome = []
            for path in ("uart", "call"):
                x = lab.fork()
                if path == "uart":
                    x.m.send([2, index, value >> 8, value & 255, 0])
                else:
                    x.call(KNOB, index, value, at=FRAME_SITE)
                x.run(0.3)
                outcome.append((lab.changed(before_all, lab.params(x)), hashlib.sha256(x.m.shown()).hexdigest()[:10], x.m.asserts))
            total += 1
            same = outcome[0] == outcome[1]
            equal += same
            mapping.setdefault(index, {})[value] = {hex(k): v[1] for k, v in outcome[0][0].items()}
            if not same:
                print("   differs: knob", index, "value", value, outcome)
    lab.check("knob-call-equals-uart", equal == total, dict(equal=equal, of=total, note="parameter bytes of the pattern, display, assertions"))
    own = {index: sorted({k for v in mapping[index].values() for k in v}) for index in mapping}
    lab.check("knob-parameter-offsets", all(hex(KNOB_PARAM[i]) in own[i] for i in own), own)

    # value to byte: the stored byte is value >> 1 and nothing limits it; a value that does not change value >> 1 is ignored
    sweep = {}
    for value in (0, 1, 2, 127, 128, 254, 255, 256, 300, 511, 512, 1023):
        x = lab.fork()
        x.call(KNOB, 0, value, at=FRAME_SITE)
        x.run(0.2)
        sweep[value] = lab.param(x)
    initial = lab.param(lab.fork())
    lab.check("knob-value-to-byte", all(sweep[v] == ((v >> 1) & 255 if v >> 1 else initial) for v in sweep), dict(initial=initial, byte_by_value=sweep))

    # the second part is 0x330 further
    results = {}
    for path in ("uart", "call"):
        x = lab.fork()
        x.press(0x0F, 0.3)                       # Part right: part 2
        before = lab.params(x, 0x8000)
        if path == "uart":
            x.m.send([2, 0, 0, 200, 0])
        else:
            x.call(KNOB, 0, 200, at=FRAME_SITE)
        x.run(0.3)
        after = lab.params(x, 0x8000)
        results[path] = {hex(i): after[i] for i in range(0x4900) if before[i] != after[i] and i not in lab.noise}
    lab.check("knob-second-part-offset", results["uart"] == results["call"] and hex(KNOB_PARAM[0] + PART_STRIDE) in results["call"], results)

    # other screens: the firmware routes by its screen mode, a call does what a message does
    effects = {}
    for screen in ("main", "menu", "write"):
        row = {}
        for path in ("uart", "call"):
            x = lab.fork()
            if screen == "menu":
                x.press(0x09, 0.4)
            if screen == "write":
                x.press(0x0E, 0.4)
            before = lab.params(x)
            if path == "uart":
                x.m.send([2, 0, 0, 200, 0])
            else:
                x.call(KNOB, 0, 200, at=FRAME_SITE)
            x.run(0.3)
            row[path] = (x.screen()["number"], KNOB_PARAM[0] in lab.changed(before, lab.params(x)), x.m.asserts)
        effects[screen] = row
    lab.check("knob-on-other-screens-like-uart", all(v["uart"] == v["call"] for v in effects.values()), effects)

    # the parameter window: both paths open it and it closes about 2 s after the last knob
    lifetimes = {}
    for path in ("uart", "call"):
        x = lab.fork()
        if path == "uart":
            x.m.send([2, 0, 0, 200, 0])
        else:
            x.call(KNOB, 0, 200, at=FRAME_SITE)
        opened, closed, t = None, None, 0.0
        while t < 4:
            x.run(0.1)
            t += 0.1
            window = x.screen()["window"] != 0
            if window and opened is None:
                opened = round(t, 1)
            if opened is not None and not window and closed is None:
                closed = round(t, 1)
        lifetimes[path] = (opened, closed)
    x = lab.fork()
    seen = []
    t = 0.0
    while t < 5:
        if abs(t * 2 - round(t * 2)) < 1e-6:
            x.call(KNOB, 0, 100 + int(t * 10) % 90, at=FRAME_SITE)
        x.run(0.1)
        t += 0.1
        seen.append(x.screen()["window"] != 0)
    lab.check("knob-popup-like-a-real-turn", lifetimes["uart"][0] == lifetimes["call"][0] and abs(lifetimes["uart"][1] - lifetimes["call"][1]) <= 0.15 and all(seen), dict(open_close_s=lifetimes, open_while_a_call_every_half_second=all(seen)))

    # the inner handler's last two arguments do not keep the window from opening, and the apply primitive alone sets nothing
    inner = {}
    for notify, sequencer in ((1, 0), (0, 0), (0, 1), (1, 1)):
        x = lab.fork()
        x.m.uc.mem_write(CODE, lab.asm.sections[0][1])
        x.m.uc.ctl_flush_tb()
        x.call(lab.asm.symbols["knob_inner"], 0, 200, notify, sequencer, at=FRAME_SITE)
        x.run(0.3)
        inner["notify=%d,sequencer=%d" % (notify, sequencer)] = (x.screen()["window"] != 0, lab.param(x))
    x = lab.fork()
    x.call(0xC0041E64, lab.obj, 0, 200, at=FRAME_SITE)
    x.run(0.3)
    alone = (x.screen()["window"] != 0, lab.param(x))
    lab.check("knob-inner-handler-arguments-do-not-hide-the-window", all(v == (True, 100) for v in inner.values()) and alone == (False, 52), dict(inner_handler=inner, apply_primitive_alone=alone))

    # a storm: all eleven knobs in every frame for five seconds; the firmware keeps answering the panel
    x = lab.fork()
    for frame in range(125):
        for index in range(11):
            x.call(KNOB, index, (frame * 7 + index * 23) & 255, at=FRAME_SITE)
        x.run(0.04)
    x.run(2.5)
    x.press(0x09, 0.5)
    lab.check("knob-storm-11-per-frame-5s", not x.m.asserts and x.screen()["number"] == 3, dict(asserts=x.m.asserts, screen=x.screen()))


def touch(lab):
    """2. Touchpad gestures from inside the firmware, with MASTER FX and without."""
    print("\n== touch: key 0x22 down, touch (x, y) moves, key 0x22 up ==")
    points = [(200, 300), (300, 350), (400, 400), (500, 500), (600, 650), (700, 800), (100, 100), (900, 900)]

    def gesture(path, mode):
        x = lab.fork()
        if mode == "mfx":
            x.press(0x06, 0.3)
        trace = [("start", x.read(lab.pat + MFX_XY, 4).hex(), x.u32(0xC06B20F0))]
        key = (lambda k, down: x.m.send([0, k, down, 0, 0])) if path == "uart" else (lambda k, down: x.call(KEY, k, down, at=FRAME_SITE))
        move = (lambda px, py: x.m.send([5, px >> 8, px & 255, py >> 8, py & 255])) if path == "uart" else (lambda px, py: x.call(TOUCH, px, py, at=FRAME_SITE))
        key(0x22, 1)
        x.run(0.1)
        for px, py in points:
            move(px, py)
            x.run(0.15)
            trace.append(((px, py), x.read(lab.pat + MFX_XY, 4).hex(), x.u32(0xC06B20F0), hashlib.sha256(x.m.shown()).hexdigest()[:8]))
        key(0x22, 0)
        x.run(0.3)
        trace.append(("up", x.read(lab.pat + MFX_XY, 4).hex(), x.u32(0xC06B20F0)))
        return trace, x.m.asserts

    for mode in ("mfx", "scale"):
        (a, asserts_a), (b, asserts_b) = gesture("uart", mode), gesture("call", mode)
        lab.check("touch-" + mode + "-call-equals-uart", a == b and not asserts_a and not asserts_b, dict(first=a[1], last=a[-2], up=a[-1]))
        if mode == "mfx":
            xs = [int(t[1][4:6], 16) for t in a[1:-1]]
            ys = [int(t[1][6:8], 16) for t in a[1:-1]]
            lab.check("touch-mfx-xy-bytes", xs == [24, 36, 50, 62, 74, 86, 12, 112] and ys[:3] == [36, 42, 50],
                      dict(x=xs, y=ys, flag_while_down=a[1][1][:2], flag_after_up=a[-1][1][:2]))

    # the MASTER FX key is a latch: pressed and released it leaves the pad in MFX mode
    x = lab.fork()
    x.press(0x06, 0.3)
    leds = dict(x.m.leds)
    lab.check("touch-master-fx-latches", leds.get(0x1C) == 255 and leds.get(0x1B) == 0, dict(master_fx_led=leds.get(0x1C), touch_scale_led=leds.get(0x1B)))

    # during REC and PLAY the firmware records a gesture in MASTER FX mode into motion lanes, and in scale mode notes; same for both paths
    recorded = {}
    for mode in ("mfx", "scale"):
        for path in ("uart", "call"):
            x = lab.fork()
            if mode == "mfx":
                x.press(0x06, 0.3)
            before = lab.params(x, 0x10000)
            x.press(0x00, 0.2)
            x.press(0x02, 0.2)
            key = (lambda k, down: x.m.send([0, k, down, 0, 0])) if path == "uart" else (lambda k, down: x.call(KEY, k, down, at=FRAME_SITE))
            move = (lambda px, py: x.m.send([5, px >> 8, px & 255, py >> 8, py & 255])) if path == "uart" else (lambda px, py: x.call(TOUCH, px, py, at=FRAME_SITE))
            key(0x22, 1)
            for k in range(12):
                move(200 + 50 * k, 300 + 40 * k)
                x.run(0.1)
            key(0x22, 0)
            x.press(0x01, 0.3)
            after = lab.params(x, 0x10000)
            changed = [i for i in range(0x10000) if before[i] != after[i] and i not in lab.noise]
            recorded[mode, path] = dict(registry=after[0x104:0x107].hex() + "/" + after[0x11C:0x11F].hex(), lanes=[len([b for b in after[0x137 + 0x40 * n:0x177 + 0x40 * n] if b]) for n in range(3)],
                                        notes=len([i for i in changed if 0x850 <= i < 0xC00]), first=sorted({hex(i) for i in changed if i < 0x900})[:8])
    lab.check("touch-rec-mfx-lanes-same-for-both-paths", recorded["mfx", "uart"]["registry"] == recorded["mfx", "call"]["registry"] and all(abs(a - b) <= 4 and a > 8 for a, b in zip(recorded["mfx", "uart"]["lanes"], recorded["mfx", "call"]["lanes"])), {k[1]: v for k, v in recorded.items() if k[0] == "mfx"})
    lab.check("touch-rec-scale-notes-same-for-both-paths", recorded["scale", "uart"]["notes"] > 30 and abs(recorded["scale", "uart"]["notes"] - recorded["scale", "call"]["notes"]) <= 15, {k[1]: v for k, v in recorded.items() if k[0] == "scale"})


def motion(lab):
    """3. Motion Sequence per part: where it lives, how to read and set it, and what it does with injected knobs."""
    print("\n== motion: recording, the per-part mode byte, conflicts ==")
    # a) the mode byte: menu page 21 (Part: MOTION SEQ), turns of the main wheel
    x = lab.fork()
    x.press(0x09, 0.4)
    for _ in range(20):
        x.press(0x0C, 0.2)
    seen = []
    for turn in (1, 1, -1, -1, -1):
        x.m.send([1, 0, 0, turn & 255, 0])
        x.run(0.3)
        seen.append(x.read(lab.pat + MOTION_MODE, 1)[0])
    copy = x.read(lab.pat + MOTION_MODE + MOTION_COPY, 1)[0]
    lab.check("motion-mode-byte", seen == [2, 2, 1, 0, 0] and copy == 0, dict(byte_after_turns=seen, copy=copy, labels="1 Smooth (start), 2 Trigger Hold, 0 Off"))
    per_part = {}
    for part in (0, 1, 2, 5):
        x = lab.fork()
        for _ in range(part):
            x.press(0x0F, 0.3)
        before = lab.params(x, 0x8000)
        x.press(0x09, 0.4)
        for _ in range(20):
            x.press(0x0C, 0.2)
        x.m.send([1, 0, 0, 1, 0])
        x.run(0.3)
        changed = lab.changed(before, lab.params(x, 0x8000), 0x5000)
        per_part[part + 1] = sorted(hex(k) for k, v in changed.items() if v == (1, 2) and (k < 0x2000 or k < 0x4200))
    lab.check("motion-mode-byte-per-part-and-copy", all(per_part[p + 1] == sorted([hex(MOTION_MODE + PART_STRIDE * p), hex(MOTION_MODE + MOTION_COPY + 0x24 * p)]) for p in (0, 1, 2, 5)),
              dict(byte_and_copy_by_part=per_part, stride_byte=hex(PART_STRIDE), stride_copy="0x24"))

    # the transport word during REC: 3 after REC, 4 after PLAY, 5 once the firmware has taken an input; a call does what a message does
    states = {}
    for path in ("uart", "call"):
        x = lab.fork()
        x.press(0x00, 0.2)
        a = x.u32(TRANSPORT)
        x.press(0x02, 0.2)
        b = x.u32(TRANSPORT)
        if path == "uart":
            x.m.send([2, 0, 0, 200, 0])
        else:
            x.call(KNOB, 0, 200, at=FRAME_SITE)
        x.run(0.3)
        c = x.u32(TRANSPORT)
        x.press(0x01, 0.3)
        states[path] = (a, b, c, x.u32(TRANSPORT))
    lab.check("motion-transport-3-4-5-0", states["uart"] == states["call"] == (3, 4, 5, 0), states)

    # b) record: the same sweep, injected by the frame stub during REC (steps 16 to 31) and by UART messages in the same steps
    sweep = [(8 * k + 16) % 250 for k in range(16)]
    recorded = {}
    for path in ("call", "uart"):
        x = lab.fork()
        if path == "call":
            lab.install(x, lanes=[(0, sweep)], length=16, record=True)
        x.press(0x00, 0.2)
        x.press(0x02, 0.0)
        if path == "call":
            lab.arm(x)
            x.run(3.4)
        else:
            k, last, t = 0, None, 0.0
            while t < 3.4:
                x.run(0.005)
                t += 0.005
                s = x.u32(STEP)
                if s != last:
                    last = s
                    if 16 <= s < 32:
                        x.m.send([2, 0, 0, sweep[s - 16], 0])
        x.press(0x01, 0.3)
        after = lab.params(x, 0x10000)
        recorded[path] = {hex(i): after[i] for i in range(0x100, 0x200) if after[i]}
    summary = {path: dict(registry=(recorded[path].get("0x104"), recorded[path].get("0x11c")), lane=[b for h, b in sorted(recorded[path].items()) if int(h, 16) >= 0x137]) for path in recorded}
    lab.check("motion-rec-same-lane-for-both-paths", summary["call"]["registry"] == summary["uart"]["registry"] and abs(len(summary["call"]["lane"]) - len(summary["uart"]["lane"])) <= 3 and len(summary["call"]["lane"]) >= 12, summary)
    values = summary["call"]["lane"]
    lab.check("motion-rec-byte-is-half-plus-one", all((b - 1) * 2 in sweep or (b - 1) * 2 + 1 in sweep for b in values), dict(sweep=sweep, recorded_decoded=[(b - 1) * 2 for b in values]))

    # c) play the recorded motion with the mode byte written into RAM before PLAY, in one copy, both copies, another part.
    #    The firmware's motion playback does not touch the stored parameter byte; its output for lane 0 is the word MOTION_OUT.
    base = lab.fork()
    lab.install(base, lanes=[(0, sweep)], length=16, record=True)
    base.press(0x00, 0.2)
    base.press(0x02, 0.0)
    lab.arm(base)
    base.run(3.4)
    base.press(0x01, 0.3)
    base.m.uc.mem_write(STATE, bytes(4))
    snap = base.m.snapshot()

    def engine(x, seconds=3.4, live=None):
        seen, last, t = {}, None, 0.0
        while t < seconds:
            x.run(0.01)
            t += 0.01
            s = x.u32(STEP)
            if s != last:
                last = s
                if live and s == live[0]:
                    for off in live[1]:
                        x.m.uc.mem_write(lab.pat + off, bytes([live[2]]))
                if 15 <= s < 33:
                    seen[s] = x.u32(MOTION_OUT)
        return seen

    variants = {"smooth": ([], 1), "off, both copies": ([MOTION_MODE, MOTION_MODE + MOTION_COPY], 0), "off, 0x807 only": ([MOTION_MODE], 0),
                "off, copy only": ([MOTION_MODE + MOTION_COPY], 0), "hold, both copies": ([MOTION_MODE, MOTION_MODE + MOTION_COPY], 2),
                "off, part 2 only": ([MOTION_MODE + PART_STRIDE, MOTION_MODE + PART_STRIDE + MOTION_COPY], 0)}
    outputs = {}
    for label, (offsets, value) in variants.items():
        x = lab.fork(snap)
        for off in offsets:
            x.m.uc.mem_write(lab.pat + off, bytes([value]))
        x.press(0x02, 0.0)
        outputs[label] = engine(x)
    distinct = {k: len({v for s, v in o.items() if 16 <= s < 32 and v != 0xFFFFFFFF}) for k, o in outputs.items()}
    lab.check("motion-engine-follows-the-recorded-lane", [outputs["smooth"][s] for s in range(16, 32)] == [v >> 1 for v in sweep],
              dict(engine_word=hex(MOTION_OUT), by_step=[outputs["smooth"][s] for s in range(16, 32)], sweep_half=[v >> 1 for v in sweep]))
    lab.check("motion-ram-mode-byte-off-silences-playback", distinct["off, both copies"] == 0 and distinct["off, 0x807 only"] == 0 and distinct["smooth"] >= 12, distinct)
    lab.check("motion-ram-mode-byte-is-0x807-not-the-copy", distinct["off, copy only"] == distinct["smooth"] and distinct["off, part 2 only"] == distinct["smooth"] and distinct["hold, both copies"] >= 12, distinct)

    # the same byte switched while playing: silent from the next step on
    x = lab.fork(snap)
    x.press(0x02, 0.0)
    live = engine(x, live=(24, [MOTION_MODE], 0))
    lab.check("motion-ram-mode-byte-live", [live[s] for s in range(16, 24)] == [v >> 1 for v in sweep[:8]] and {live[s] for s in range(25, 32)} <= {0xFFFFFFFF, live[24]},
              {s: hex(v) for s, v in live.items() if s >= 20})

    # d) conflict: the firmware plays its lane (Smooth) and the stub injects another sweep in the same steps. The injection goes to the stored
    #    parameter byte and silences the lane like a hand on the knob; a few steps after the last change the lane plays again.
    #    A constant injected value is ignored by the firmware after the first call (same value), so the override then times out.
    def conflict(values):
        x = lab.fork(snap)
        lab.install(x, lanes=[(0, values)], length=16)
        x.press(0x02, 0.0)
        lab.arm(x)
        seen, params, last, t = {}, set(), None, 0.0
        while t < 5.0:
            x.run(0.005)
            t += 0.005
            s = x.u32(STEP)
            if s != last:
                last = s
                if 16 <= s < 64:
                    seen[s] = x.u32(MOTION_OUT)
            if 16 <= (last or 0) < 32:
                params.add(lab.param(x))
        return seen, params, lab.state(x, 48)

    moving, params, injections = conflict(sweep[::-1][:10])        # ten distinct values, steps 16 to 25
    silent = [s for s in sorted(moving) if 17 <= s < 32 and moving[s] == 0xFFFFFFFF]
    resumed = [s for s in sorted(moving) if s >= 26 and moving[s] != 0xFFFFFFFF]
    lab.check("motion-moving-injection-silences-the-lane-then-it-resumes",
              injections == 10 and silent[:1] == [18] and all(s in silent for s in range(18, 27)) and resumed and 29 <= resumed[0] <= 36 and (sweep[::-1][0] >> 1) in params,
              dict(lane_silent_steps=silent, lane_back_at_step=resumed[:1], last_injection_step=25, injections=injections, parameter_byte_values=sorted(params)))
    constant, params, injections = conflict([200] * 16)
    lab.check("motion-constant-injection-is-ignored-after-the-first-call", [s for s in sorted(constant) if s < 40 and constant[s] == 0xFFFFFFFF] != [] and constant[28] != 0xFFFFFFFF and 100 in params,
              dict(engine_by_step={s: (hex(v) if v == 0xFFFFFFFF else v) for s, v in constant.items() if s < 34}, injections=injections))
    x = lab.fork(snap)
    for off in (MOTION_MODE, MOTION_MODE + MOTION_COPY):
        x.m.uc.mem_write(lab.pat + off, bytes([0]))
    lab.install(x, lanes=[(0, [200] * 16)], length=16)
    x.press(0x02, 0.0)
    lab.arm(x)
    x.run(3.4)
    lab.check("motion-off-then-injection-alone", lab.param(x) == 100 and x.u32(MOTION_OUT) == 0xFFFFFFFF and not x.m.asserts, dict(parameter=lab.param(x), engine=hex(x.u32(MOTION_OUT))))

    # e) REC armed while the stub plays: the firmware records the injection, so the plugin must keep it out of REC
    x = lab.fork()
    lab.install(x, lanes=[(0, sweep)], length=16, record=False)
    x.press(0x00, 0.2)
    x.press(0x02, 0.0)
    lab.arm(x)
    x.run(3.4)
    x.press(0x01, 0.3)
    lab.check("motion-rec-without-record-flag-injects-nothing", lab.state(x, 48) == 0 and not any(lab.params(x, 0x10000)[0x100:0x200]), dict(injections=lab.state(x, 48)))


def gate(lab):
    """3b. Play a recorded firmware lane on demand by switching the part's MOTION SEQ byte, no injection at all."""
    print("\n== gate: the part's motion mode byte as an on/off switch for the firmware's own lanes ==")
    sweep = [(8 * k + 16) % 250 for k in range(16)]
    pat = lab.pat

    def record(part=0, mode_before=None, via="uart"):
        x = lab.fork()
        if part:
            x.press(0x0F, 0.3)
        if mode_before is not None:
            for off in (MOTION_MODE, MOTION_MODE + MOTION_COPY):
                x.m.uc.mem_write(pat + off + PART_STRIDE * part, bytes([mode_before]))
        x.press(0x00, 0.2)
        x.press(0x02, 0.0)
        last, t = None, 0.0
        while t < 3.4:
            x.run(0.005)
            t += 0.005
            st = x.u32(STEP)
            if st != last:
                last = st
                if 16 <= st < 32:
                    x.m.send([2, 0, 0, sweep[st - 16], 0])
        x.press(0x01, 0.5)
        return x

    def lane(x):
        data = x.read(pat + 0x134, 0x40)
        return [b for b in data if b]

    # a) recording while the part's mode is Off: does the firmware record at all
    for mode in (1, 0, 2):
        x = record(mode_before=mode)
        got = lane(x)
        lab.check("gate-rec-with-mode-%d" % mode, True, dict(mode=mode, lane_bytes=len(got), registry=x.read(pat + 0x104, 1).hex() + "/" + x.read(pat + 0x11C, 1).hex(), first=got[:4]))
    smooth = record(mode_before=1)
    snap = smooth.m.snapshot()

    # b) switch on and off while playing, at bar boundaries (16 and 32) as a plugin would
    y = lab.fork(snap)
    for off in (MOTION_MODE, MOTION_MODE + MOTION_COPY):
        y.m.uc.mem_write(pat + off, bytes([0]))
    y.press(0x02, 0.0)
    seen, last, t = {}, None, 0.0
    while t < 3.8:
        y.run(0.01)
        t += 0.01
        st = y.u32(STEP)
        if st != last:
            last = st
            if st == 16:
                for off in (MOTION_MODE, MOTION_MODE + MOTION_COPY):
                    y.m.uc.mem_write(pat + off, bytes([1]))
            if st == 24:
                for off in (MOTION_MODE, MOTION_MODE + MOTION_COPY):
                    y.m.uc.mem_write(pat + off, bytes([0]))
            if 14 <= st < 32:
                seen[st] = y.u32(MOTION_OUT)
    on = [s for s in sorted(seen) if seen[s] != 0xFFFFFFFF]
    lab.check("gate-switch-on-at-the-bar-and-off-again", on and on[0] <= 17 and on[-1] <= 25 and len(on) >= 6 and all(seen[s] == sweep[s - 16] >> 1 for s in on if s >= 16),
              dict(lane_audible_steps=on, values=[seen[s] for s in on]))

    # c) part 2 has its own lane and its own switch
    x2 = record(part=1)
    flag, target = x2.read(pat + 0x104, 1)[0], x2.read(pat + 0x11C, 1)[0]
    snap2 = x2.m.snapshot()
    rows = {}
    for label, writes in {"part 2 on": [], "part 2 off": [(MOTION_MODE + PART_STRIDE, 0)], "part 1 off": [(MOTION_MODE, 0)]}.items():
        z = lab.fork(snap2)
        for off, v in writes:
            z.m.uc.mem_write(pat + off, bytes([v]))
        z.press(0x02, 0.0)
        seen, last, t = set(), None, 0.0
        while t < 3.4:
            z.run(0.01)
            t += 0.01
            st = z.u32(STEP)
            if st != last:
                last = st
                if 16 <= st < 32 and z.u32(MOTION_OUT) != 0xFFFFFFFF:
                    seen.add(z.u32(MOTION_OUT))
        rows[label] = len(seen)
    lab.check("gate-part-two-has-its-own-switch", rows["part 2 on"] >= 12 and rows["part 2 off"] == 0 and rows["part 1 off"] >= 12, dict(distinct_values=rows, registry_flag=flag, registry_target=target))

    # d) a recorded MASTER FX gesture sits in three more lanes; the part's byte does not switch them
    x = lab.fork()
    x.press(0x06, 0.3)
    x.press(0x00, 0.2)
    x.press(0x02, 0.0)
    last, t, down = None, 0.0, False
    while t < 3.4:
        x.run(0.005)
        t += 0.005
        st = x.u32(STEP)
        if st != last:
            last = st
            if 16 <= st < 32:
                if not down:
                    x.m.send([0, 0x22, 1, 0, 0])
                    down = True
                px, py = 200 + 40 * (st - 16), 300 + 30 * (st - 16)
                x.m.send([5, px >> 8, px & 255, py >> 8, py & 255])
            elif st >= 32 and down:
                x.m.send([0, 0x22, 0, 0, 0])
                down = False
    x.press(0x01, 0.5)
    snap3 = x.m.snapshot()
    rows = {}
    for label, writes in {"part byte on": [], "part byte off": [(MOTION_MODE, 0), (MOTION_MODE + MOTION_COPY, 0)]}.items():
        z = lab.fork(snap3)
        for off, v in writes:
            z.m.uc.mem_write(pat + off, bytes([v]))
        z.press(0x02, 0.0)
        seen, last, t = set(), None, 0.0
        while t < 3.4:
            z.run(0.01)
            t += 0.01
            st = z.u32(STEP)
            if st != last:
                last = st
                if 16 <= st < 32:
                    seen.add(tuple(z.u32(MOTION_OUT + 4 * i) for i in range(2)))
        rows[label] = len(seen)
    lab.check("gate-mfx-lanes-ignore-the-part-byte", rows["part byte on"] >= 12 and rows["part byte off"] == rows["part byte on"], dict(distinct_x_y_outputs=rows, registry=x.read(pat + 0x11C, 3).hex()))
    # nothing else found switches them either: the lane's part mask and its target in the registry
    switched = {}
    for label, writes in {"mask 0": [(0x104 + i, 0) for i in range(3)], "mask 1": [(0x104 + i, 1) for i in range(3)], "mask 0x10": [(0x104 + i, 0x10) for i in range(3)],
                          "target 0xff": [(0x11C + i, 0xFF) for i in range(3)]}.items():
        z = lab.fork(snap3)
        for off, v in writes:
            z.m.uc.mem_write(pat + off, bytes([v]))
        z.press(0x02, 0.0)
        seen, last, t = set(), None, 0.0
        while t < 3.4:
            z.run(0.01)
            t += 0.01
            st = z.u32(STEP)
            if st != last:
                last = st
                if 16 <= st < 32:
                    seen.add(tuple(z.u32(MOTION_OUT + 4 * i) for i in range(2)))
        switched[label] = len(seen)
    lab.check("gate-mfx-registry-writes-do-not-switch-them", all(n >= 12 for n in switched.values()), switched)


def bar(lab):
    """4. Bar timing."""
    print("\n== bar: step counter, bar length, start quantised to the next bar ==")
    slots = {}
    for code in range(4):
        x = lab.fork()
        if code:
            lab.setpage(x, 3, [1] * code)
        x.press(0x02, 0.01)
        rows = lab.watch(x, 6.4)
        seq = [(t / 1000, s) for t, s, _ in rows]
        values = [s for _, s in seq]
        wrap = [t for (t0, a), (t, b) in zip(seq, seq[1:]) if b < a]
        periods = [round((t1 - t0) * 1000) for (t0, a), (t1, b) in zip(seq, seq[1:]) if b == a + 1]
        slots[code] = dict(beat_byte=x.read(lab.pat + BEAT, 1)[0], max=max(values), step_ms=statistics.median(periods), wrap_at_s=wrap[:2],
                           jumps=sorted({b - a for (_, a), (_, b) in zip(seq, seq[1:]) if b > a}))
    lab.check("bar-counter-16-slot-groups", slots[0]["max"] == 63 and slots[0]["wrap_at_s"][0] > 5.9 and slots[2]["jumps"] == [1, 5] and slots[3]["jumps"] == [1, 5], slots)
    lab.check("bar-beat-32-has-32-slots-per-bar", slots[1]["max"] == 63 and 2.9 < slots[1]["wrap_at_s"][0] < 3.0, slots[1])

    # every part has its own counter: with LAST STEP 8 on part 1 its counter runs 0 to 7, then 16 to 23, and its bars are 8 steps long;
    # the other parts count on, so a bar is only defined by a part with LAST STEP 16
    x = lab.fork()
    before = lab.params(x, 0x1000)
    lab.setpage(x, 16, [8])
    changed = lab.changed(before, lab.params(x, 0x1000), 0x1000)
    x.press(0x02, 0.01)
    rows, last, t = [], None, 0.0
    while t < 3.2:
        x.run(0.01)
        t += 0.01
        now = (x.u32(STEP), x.u32(STEP + 0x48), x.u32(STEP + 0x48 * 2))
        if now != last:
            rows.append(now)
            last = now
    short = [r[0] for r in rows]
    lab.check("bar-counter-is-per-part-and-last-step-shortens-it", set(changed) == {0x804} and changed[0x804] == (0, 8) and short[:10] == [0, 1, 2, 3, 4, 5, 6, 7, 16, 17]
              and [r[1] for r in rows][:12] == list(range(12)),
              dict(last_step_byte=changed, part1_counter=short[:20], part2_counter=[r[1] for r in rows][:20], wraps_at=[r[0] for r in rows if r[0] < 16][8:12]))

    # start at the next bar: TAP in the middle of a bar, the frame stub starts at the next bar and injects
    sweep = [(8 * k + 16) % 250 for k in range(16)]
    rows = []
    for offset in (0.0, 0.3, 0.7, 1.1, 1.4):
        x = lab.fork()
        lab.install(x, lanes=[(0, sweep)], length=16, drop_tap=True)
        x.press(0x02, 0.01)
        x.run(0.2 + offset)
        step_at_tap = x.u32(STEP)
        lab.tap(x)
        trace = lab.watch(x, 2.4)
        started = lab.state(x, 44)
        t_bar = next((t for t, s, b in trace if s == started), None)
        t_param = next((t for t, s, b in trace if s >= started and b == sweep[0] >> 1), None)
        rows.append(dict(step_at_tap=step_at_tap, started_at_step=started, bar_to_first_value_ms=(t_param - t_bar) if t_bar is not None and t_param is not None else None,
                         dropped_taps=lab.state(x, 32)))
    lab.check("bar-start-is-the-next-bar", all(r["started_at_step"] % 16 == 0 and r["started_at_step"] > r["step_at_tap"] - r["step_at_tap"] % 16 for r in rows), rows)
    lab.check("bar-start-late-by-at-most-a-frame", all(r["bar_to_first_value_ms"] is not None and 0 <= r["bar_to_first_value_ms"] <= 50 for r in rows), [r["bar_to_first_value_ms"] for r in rows])

    # how many steps does a 40 ms frame miss
    misses = {}
    for label, code, tenths in (("beat16-160", 0, 1600), ("beat16-300", 0, 3000), ("beat32-160", 1, 1600), ("beat32-300", 1, 3000)):
        x = lab.fork()
        if code:
            lab.setpage(x, 3, [1] * code)
        x.call(TEMPO_SET, lab.pat, tenths, 1, at=FRAME_SITE)
        x.run(0.1)
        x.press(0x02, 0.01)
        last, missed, bar_missed, t = None, 0, 0, 0.0
        shift = 4 + (code & 1)
        while t < 8.0:
            x.run(0.04)
            t += 0.04
            s = x.u32(STEP)
            if last is not None and s != last:
                ahead = (s - last) % 64
                missed += max(0, ahead - 1)
                if ahead > 1 and (s >> shift) == (last >> shift) and s % (1 << shift) != 0 and (last % (1 << shift)) > (s % (1 << shift)):
                    bar_missed += 1
            last = s
        misses[label] = dict(missed_steps_in_8s=missed, tempo=x.u32(TEMPO))
    lab.check("bar-frame-misses-steps-only-when-steps-are-shorter-than-a-frame", misses["beat16-160"]["missed_steps_in_8s"] == 0 and misses["beat16-300"]["missed_steps_in_8s"] == 0 and misses["beat32-300"]["missed_steps_in_8s"] > 0, misses)


def tap(lab):
    """5. TAP and SHIFT+TAP."""
    print("\n== tap: tap tempo, SHIFT, dropping TAP in the input filter ==")

    def taps(x, n=4, gap=0.65):
        for _ in range(n):
            lab.tap(x)
            x.run(gap - 0.05)
        x.run(0.3)

    x = lab.fork()
    taps(x)
    plain = lab.tempo(x)
    x = lab.fork()
    x.m.send([0, 10, 1, 0, 0])
    x.run(0.1)
    taps(x)
    x.m.send([0, 10, 0, 0, 0])
    shifted = lab.tempo(x)
    lab.check("tap-stock-plain-sets-tempo", plain == 923, plain)
    lab.check("tap-stock-shift-tap-sets-nothing", shifted == 1600, shifted)

    a, b = lab.fork(), lab.fork()
    a.m.send([0, 10, 1, 0, 0])
    a.run(0.1)
    a.m.send([0, 3, 1, 0, 0])
    a.run(0.3)
    a.m.send([0, 3, 0, 0, 0])
    a.m.send([0, 10, 0, 0, 0])
    a.run(0.3)
    b.run(0.7)
    lab.check("tap-stock-shift-tap-opens-the-bpm-page", a.screen()["number"] == 3 and b.screen()["number"] == 1 and lab.tempo(a) == 1600 and not lab.changed(lab.params(b), lab.params(a)),
              dict(screen_with_shift_tap=a.screen()["number"], screen_without=b.screen()["number"], tempo=lab.tempo(a)))

    # the stub drops a plain TAP and a SHIFT+TAP, tracks SHIFT, lets every other key through
    x = lab.fork()
    lab.install(x, drop_tap=True, frame=False)
    taps(x)
    lab.check("tap-stub-drops-plain-tap", lab.tempo(x) == 1600 and lab.state(x, 32) == 4 and lab.state(x, 8) == 1, dict(tempo=lab.tempo(x), plain_taps=lab.state(x, 32)))
    x.m.send([0, 10, 1, 0, 0])
    x.run(0.1)
    taps(x, 3)
    shift_down = lab.state(x, 28)
    x.m.send([0, 10, 0, 0, 0])
    x.run(0.1)
    lab.check("tap-stub-sees-shift-tap", lab.state(x, 40) == 3 and lab.state(x, 32) == 4 and shift_down == 1 and lab.state(x, 28) == 0 and lab.tempo(x) == 1600,
              dict(shift_taps=lab.state(x, 40), plain_taps=lab.state(x, 32), tempo=lab.tempo(x)))
    y = lab.fork()
    lab.install(y, drop_tap=True, frame=False)
    before = y.read(0xC06B2428, 4)
    y.press(0x0F, 0.3)
    lab.check("tap-stub-other-keys-pass", y.read(0xC06B2428, 4) != before and not y.m.asserts, y.read(0xC06B2428, 4).hex())
    z = lab.fork()
    lab.install(z, drop_tap=False, frame=False)
    taps(z)
    lab.check("tap-stub-without-drop-flag-is-the-stock-behaviour", lab.tempo(z) == 923, lab.tempo(z))

    # tap tempo done by the plugin: the firmware's tempo setter with the average interval, what korg.tempo calls
    intervals = [0.65, 0.65, 0.65]
    tenths = round(600 / (sum(intervals) / len(intervals)))
    x = lab.fork()
    x.call(TEMPO_SET, lab.pat, tenths, 1, at=FRAME_SITE)
    x.run(0.2)
    lab.check("tap-plugin-side-tap-tempo-matches-the-firmware", lab.tempo(x) == plain == 923, dict(computed=tenths, tempo=lab.tempo(x), stock_tap=plain))


def cost(lab):
    """Cost of the calls: instructions of the firmware function alone, and the slowest call in the frame stub in Timer3 ticks."""
    print("\n== cost ==")
    x = lab.fork()
    counts = {}
    for index in range(11):
        counts[index] = lab.pure_call(x, KNOB, index, 150)[0]
        x.run(0.04)
    same = lab.pure_call(x, KNOB, 10, 150)[0]
    lab.check("cost-knob-instructions", max(counts.values()) < 6000 and same < 400, dict(by_knob=counts, same_value_again=same))
    y = lab.fork()
    y.press(0x06, 0.3)
    c = {"key": lab.pure_call(y, KEY, 0x0D, 0)[0], "key_0x22_down": lab.pure_call(y, KEY, 0x22, 1)[0]}
    for point in ((400, 400), (410, 410)):
        c["touch_" + str(point)] = lab.pure_call(y, TOUCH, *point)[0]
        y.run(0.04)
    c["key_0x22_up"] = lab.pure_call(y, KEY, 0x22, 0)[0]
    c["tempo_set"] = lab.pure_call(y, TEMPO_SET, lab.pat, 1500, 1)[0]
    lab.check("cost-other-calls-instructions", max(c.values()) < 20000, c)

    sweep = [(8 * k + 16) % 250 for k in range(16)]
    x = lab.fork()
    lab.install(x, lanes=[(i, sweep) for i in range(11)], length=16)
    x.press(0x02, 0.01)
    lab.arm(x)
    x.run(3.4)
    ticks = lab.state(x, 52)
    lab.check("cost-eleven-knobs-one-bar-in-the-frame-stub", lab.state(x, 48) >= 11 * 15 and not x.m.asserts,
              dict(injections=lab.state(x, 48), slowest_single_call_ticks=ticks, slowest_single_call_ms=round(ticks / 150000, 3), note="includes interrupts and task switches that hit the call"))


def runtime(lab):
    """6. What the real plugin runtime's input filter does with TAP: a plugin sees it, the firmware gets it as well, and the only
    switch is for a whole class of messages."""
    print("\n== runtime: the existing input filter (tools/patch/script_hooks.s, not changed) with a plugin that counts keys ==")
    import script_cases
    from tools.patch import script_hooks
    node = subprocess.run(["node", str(Path(__file__).with_name("tap_motion_request.mjs"))], capture_output=True, text=True, timeout=60)
    if node.returncode:
        print("   node failed:", node.stderr[:300])
        lab.check("runtime-request", False, node.stderr[:300])
        return
    request = json.loads(node.stdout)
    built = script_hooks.build(request["include"])
    patched = built.apply(script_cases.baseline(lab.vsb))
    program = request["programs"]["tapwatch"]

    def device(mask):
        dev = Dev(patched[0x100:], lab.flash)
        dev.run(2)
        entries = script_cases.install(dev, built, request["programs"], ["tapwatch"], mask=mask)
        dev.run(0.2)
        return dev, entries

    def watch(dev, entries):
        return script_cases.variables(dev, entries["tapwatch"], program)

    rows = {}
    for mask in (0, 1):
        dev, entries = device(mask)
        for _ in range(4):
            dev.m.send([0, 3, 1, 0, 0])
            dev.run(0.05)
            dev.m.send([0, 3, 0, 0, 0])
            dev.run(0.6)
        dev.run(0.3)
        tempo = dev.u32(TEMPO)
        part = dev.read(0xC06B2428, 4).hex()
        dev.press(0x0F, 0.3)
        rows[mask] = dict(plugin=watch(dev, entries), tempo_after_4_taps=tempo, part_before=part, part_after_part_key=dev.read(0xC06B2428, 4).hex(), asserts=dev.m.asserts)
    lab.check("runtime-mask-0-plugin-sees-tap-and-firmware-takes-it", rows[0]["plugin"]["taps"] == 4 and rows[0]["tempo_after_4_taps"] == 923 and rows[0]["plugin"]["others"] == 1
              and rows[0]["part_after_part_key"] != rows[0]["part_before"], rows[0])
    lab.check("runtime-mask-1-drops-every-key-not-only-tap", rows[1]["plugin"]["taps"] == 4 and rows[1]["tempo_after_4_taps"] == 1600 and rows[1]["part_after_part_key"] == rows[1]["part_before"]
              and rows[1]["plugin"]["others"] == 1, rows[1])
    dev, entries = device(0)
    dev.m.send([0, 10, 1, 0, 0])
    dev.run(0.1)
    dev.m.send([0, 3, 1, 0, 0])
    dev.run(0.3)
    dev.m.send([0, 3, 0, 0, 0])
    dev.m.send([0, 10, 0, 0, 0])
    dev.run(0.3)
    seen = watch(dev, entries)
    lab.check("runtime-plugin-sees-shift-and-tap-in-order", seen["shifts"] == 1 and seen["taps"] == 1 and dev.screen()["number"] == 3, dict(plugin=seen, screen=dev.screen()["number"]))


ALL = dict(knob=knob, touch=touch, motion=motion, gate=gate, bar=bar, tap=tap, runtime=runtime, cost=cost)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=",".join(ALL))
    ap.add_argument("--vsb", default=os.environ.get("E2_VSB"))
    ap.add_argument("--flash", default=os.environ.get("E2_FLASH"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not args.vsb:
        sys.exit("E2_VSB is needed (your own SYSTEM.VSB); nothing of it is kept")
    vsb = Path(args.vsb).expanduser().read_bytes()
    flash = load_flash([str(Path(args.flash).expanduser())]) if args.flash else None
    lab = Lab(vsb, flash)
    print("booted in %.1f s, pattern object %#x, noise bytes %d" % (lab.boot_s, lab.pat, len(lab.noise)))
    for name in args.only.split(","):
        ALL[name](lab)
    failed = [c for c in lab.checks if not c["ok"]]
    print("\n%d checks, %d failed" % (len(lab.checks), len(failed)))
    if args.json:
        print(json.dumps(lab.checks, default=str))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
