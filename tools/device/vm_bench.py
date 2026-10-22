"""Measure the speed of a script bytecode VM on the own Electribe, RAM only.

A small ARM interpreter for a handful of script opcodes (data/script/contract.mjs,
format 2) and a few bytecode programs go to 0xC1000000, the Hacktribe upload
area, as one stub. Each run goes through Hacktribe's execute command 0x57: the
stub reads a free-running counter (TIM12 of the timer that stage 2 finds running) before and after the program,
stores ticks and operation count in RAM and returns 0. The host reads them
back, checks the program's variables against a reference run, and prints
nanoseconds per operation. The original bytes at the stub address are put
back at the end, as in led_show.py. The stub never touches the interrupt bits
(the run prints them), writes only inside the first KiB, and no run is longer
than --target-ms (10 ms by default, 2 ms when IRQ is masked). A write makes the
firmware show "Working..." for a moment; there are a few dozen of them.

Two interpreter variants are measured: "lean" (opcode fetch, one fuel
decrement, table jump, the prototype of the research) and "checked" (opcode
range check, fuel by the contract's cost table, a counter check every 256
operations, what the real VM has to do). The probes differ from the plain
counting loop by four copies of one operation pair, so one pair's cost is the
difference. LOAD8 and STORE8 are bench-only opcodes with an 8-bit slot: their
difference to LOAD and STORE is the cost of format 2's 16-bit operand.

    python3 vm_bench.py --emu VSB                    # against the local emulator
    python3 vm_bench.py --emu VSB --json emu.json    # keep the emulator numbers
    python3 vm_bench.py --dry-run                    # device on USB: checks only, writes nothing
    python3 vm_bench.py --json device.json           # device on USB: the real run
    python3 vm_bench.py --compare emu.json           # ... and the factor to the emulator
    python3 vm_bench.py --bare                       # no firmware: the stub alone in Unicorn
    python3 vm_bench.py --stages-only                # device on USB: four small executes, then stop

Before the benchmark four stages run, each as its own execute: a stub that
only returns, a mark stub at the entry offset, one that reads the timer, and
the interpreter with N = 1. A
stage that gets no ack reports how far it got from the progress word and the
result fields in RAM, restores the stub area and exits with status 2.

The ack of Hacktribe's execute goes to the port that the stub's return value r0 names (ACK_PORTS), so
every stub returns 0. The benchmark executes at 0xC1000000 like the LED stubs; the first word of the image
branches to the entry at 0xCC.

On the device the CPU data cache is on for 0xC0000000..0xC3FFFFFF (page table
of the bootloader, write-back), and the instruction fetch reads RAM, not the
cache. Right after a write the stub is therefore compared through the uncached
alias 0xC4000000 and, when that differs, the cache is pushed out by reading
--evict-kib of firmware code; nothing is executed before RAM matches.

Needs led_show.py next to it and ../patch/arm.py for the assembler (and
../emu/machine.py for --emu); mido for the device. The emulator and --bare
also count the instructions the stub executes, which the device cannot.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "patch"))

try:
    import arm
except ImportError:
    raise SystemExit("vm_bench.py needs the assembler tools/patch/arm.py (copy it to ../patch/ next to this folder)")

STUB_AT = 0xC1000000
STUB_SIZE = 0x400                       # data/exec.mjs: the first KiB is released for stubs
ICACHE_INVALIDATE = 0xC00016A4
# TIM12 at +0x10, PRD12 +0x18, TCR +0x20, TGCR +0x24. 0x01C21000 is set to watchdog mode by the firmware and
# its counter stays 0 on the device (measured 2026-10-13); the others are configured as 24 MHz, 24 MHz and
# 150 MHz counters by the firmware (period registers read in the emulator, clock rates assumed from them).
TIMER_LIST = [(0x01C20000, 24e6, "TIMER64P0, 1 kHz system tick"), (0x01C21000, 24e6, "TIMER64P1, watchdog mode"),
              (0x01F0C000, 150e6, "timer 2, 0.5 ms tick"), (0x01F0D000, 150e6, "timer 3, about 1 s period")]
TIMER = 0x01F0D000                      # the counter the stub reads; stage 2 picks it, see select_timer
TICK_NS = 1e9 / 150e6
MIN_WRAP_MS = 100                       # a timer wraps no sooner than this, so that one run never spans two wraps
PROBE_DATA = 0x40                       # stage 2 results: TGCR, TCR, PRD, before, after for each of TIMER_LIST


def select_timer(base, hz):
    global TIMER, TICK_NS
    TIMER, TICK_NS = base, 1e9 / hz
ALIAS = 0x04000000                      # 0xC4000000.. is the uncached view of 0xC0000000.. (bootloader page table)
EVICT_AT = 0xC0040000                   # firmware code: reading it only fills the data cache with clean lines
EVICT_STEP = 0x2000
CONTRACT = HERE.parent.parent / "data" / "script" / "contract.mjs"

EXPECTED = {                            # sha256 of the code the run relies on (own VSB)
    (0xC00016A4, 0x34): "f33f00d1ca5392c857af29991ed0e4e10340bb4675df9e2f030af0caf730bd6a",
    (0xC0000040, 64): "0ecfbf472eb414c359f29af80817ad36cac542fe94b1f4e3cd4fe078a50e6de0",
    (0xC017059C, 512): "94975043805a3baa09d4916636d9ba93c9ab7c367efbf7b8d8d8e1b848219470",
}

ERRORS = {0: "OK", 1: "FUEL", 2: "BAD_OPCODE", 3: "BOUNDS", 7: "TIME"}

# name: (opcode, operand sizes in bytes, fuel cost). Numbers, sizes and costs are
# the contract's; LOAD8 and STORE8 are bench-only and sit in the slots of PUSHK and PUSHS.
# The other contract opcodes are not implemented here; their slots lead to the bad-opcode exit.
OPS = {
    "HALT": (0, (), 1), "PUSHB": (1, (1,), 1), "LOAD": (4, (2,), 1), "STORE": (5, (2,), 1),
    "ALOAD": (6, (2, 2), 2), "ASTORE": (7, (2, 2), 2), "DROP": (9, (), 1),
    "ADD": (10, (), 1), "MUL": (12, (), 2), "AND": (15, (), 1),
    "LT": (24, (), 1), "GT": (26, (), 1), "JMP": (28, (2,), 1), "JZ": (29, (2,), 1),
    "LOAD8": (2, (1,), 1), "STORE8": (3, (1,), 1),
}
BENCH_ONLY = {"LOAD8", "STORE8"}
OPCODE_SLOTS = 30

VARS = 12                               # words: 0 = N, 1.. scratch, 8..11 = the array
STACK_WORDS = 4
HEAD_LEN = 56                           # inputs, results and N at the very start of the stub area (see build)
R = {"end": 4, "ops": 8, "err": 12, "vpc": 16, "cpsr": 20, "prd": 24, "tcr": 28, "prog": 32, "start": 36, "period": 48}
IN_LIMIT, IN_FUEL, IN_N = 40, 44, 52


# ---- bytecode: assembler, reference VM, programs ------------------------------------

def assemble_code(items):
    """items: ("OP", args...) tuples and "label:" strings; a jump target is a label name."""
    labels, pc, laid = {}, 0, []
    for it in items:
        if isinstance(it, str):
            labels[it.rstrip(":")] = pc
            continue
        code, sizes, _ = OPS[it[0]]
        laid.append((pc, it))
        pc += 1 + sum(sizes)
    out = bytearray(pc)
    for at, it in laid:
        code, sizes, _ = OPS[it[0]]
        out[at] = code
        p = at + 1
        for size, v in zip(sizes, it[1:]):
            v = labels[v] if isinstance(v, str) else v
            if not 0 <= v < 1 << (8 * size):
                raise ValueError(f"{it}: operand {v} does not fit {size} byte(s)")
            out[p:p + size] = v.to_bytes(size, "little")
            p += size
    return bytes(out)


def decode(code, at):
    name = next(n for n, (c, _, _) in OPS.items() if c == code[at])
    sizes = OPS[name][1]
    args, p = [], at + 1
    for size in sizes:
        args.append(int.from_bytes(code[p:p + size], "little"))
        p += size
    return name, args, p


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def reference(code, n, fuel=10 ** 9):
    """The contract's semantics for the implemented opcodes: final variables, operations, cost, histogram."""
    v, st, pc, ops, cost, hist = [0] * VARS, [], 0, 0, 0, {}
    v[0] = n
    while True:
        name, a, nxt = decode(code, pc)
        ops += 1
        cost += OPS[name][2]
        hist[name] = hist.get(name, 0) + 1
        if ops > fuel:
            raise RuntimeError("reference run exceeds its fuel")
        pc = nxt
        if name == "HALT":
            break
        elif name == "PUSHB":
            st.append(a[0])
        elif name in ("LOAD", "LOAD8"):
            st.append(v[a[0]])
        elif name in ("STORE", "STORE8"):
            v[a[0]] = st.pop()
        elif name == "ALOAD":
            i = st.pop()
            if not 0 <= i < a[1]:
                raise RuntimeError("ALOAD bounds")
            st.append(v[a[0] + i])
        elif name == "ASTORE":
            val, i = st.pop(), st.pop()
            if not 0 <= i < a[1]:
                raise RuntimeError("ASTORE bounds")
            v[a[0] + i] = val
        elif name == "DROP":
            st.pop()
        elif name == "JMP":
            pc = a[0]
        elif name == "JZ":
            if st.pop() == 0:
                pc = a[0]
        else:
            b, x = st.pop(), st.pop()
            st.append({"ADD": lambda: s32(x + b), "MUL": lambda: s32(x * b),
                       "AND": lambda: x & b, "LT": lambda: int(x < b),
                       "GT": lambda: int(x > b)}[name]())
        if len(st) > STACK_WORDS:
            raise RuntimeError("operand stack deeper than the stub's")
    return {"vars": [x & 0xFFFFFFFF for x in v], "ops": ops, "cost": cost, "hist": hist}


COPIES = 4


def counting_loop(body=()):
    """for (i = 0; i < n; i++) { body }: nine operations a round and the exit test. The stub zeroes variables 1 up."""
    return ["L:", ("LOAD", 1), ("LOAD", 0), ("LT",), ("JZ", "D"),
            *body, ("LOAD", 1), ("PUSHB", 1), ("ADD",), ("STORE", 1), ("JMP", "L"), "D:", ("HALT",)]


def probe(pair, copies=COPIES):
    """`copies` of one operation pair per round; a JMP target inside the body is a local label."""
    body = []
    for k in range(copies):
        for item in pair:
            body.append(tuple(f"J{k}" if x == "NEXT" else x for x in item))
        if any("NEXT" in item for item in pair):
            body.append(f"J{k}:")
    return counting_loop(body)


MIX = [  # a Snake-like round: ring buffer of four with array access, two compares and a branch
    "L:", ("LOAD", 1), ("LOAD", 0), ("LT",), ("JZ", "D"),
    ("LOAD", 6), ("PUSHB", 1), ("ADD",), ("PUSHB", 3), ("AND",), ("STORE", 6),
    ("LOAD", 6), ("ALOAD", 8, 4), ("STORE", 3),
    ("LOAD", 6), ("LOAD", 1), ("PUSHB", 3), ("MUL",), ("LOAD", 2), ("ADD",), ("ASTORE", 8, 4),
    ("LOAD", 3), ("LOAD", 1), ("GT",), ("JZ", "S"),
    ("LOAD", 2), ("PUSHB", 1), ("ADD",), ("STORE", 2),
    "S:", ("LOAD", 1), ("PUSHB", 1), ("ADD",), ("STORE", 1), ("JMP", "L"), "D:", ("HALT",),
]

PROGRAMS = {
    "count": counting_loop(),
    "load": probe([("LOAD", 2), ("DROP",)]),
    "load8": probe([("LOAD8", 2), ("DROP",)]),
    "push": probe([("PUSHB", 7), ("DROP",)]),
    "store": probe([("PUSHB", 7), ("STORE", 3)]),
    "store8": probe([("PUSHB", 7), ("STORE8", 3)]),
    "alu": probe([("PUSHB", 5), ("PUSHB", 3), ("ADD",), ("DROP",)]),
    "aload": probe([("PUSHB", 3), ("ALOAD", 8, 4), ("DROP",)]),
    "astore": probe([("PUSHB", 3), ("PUSHB", 9), ("ASTORE", 8, 4)]),
    "jmp": probe([("JMP", "NEXT")]),
    "jz": probe([("PUSHB", 1), ("JZ", "NEXT")]),
    "mix": MIX,
}
# What one probe unit is, for the per-operation figures: (operations in the pair, minus the matching count of the baseline).
UNIT_OPS = {"load": 2, "load8": 2, "push": 2, "store": 2, "store8": 2, "alu": 4, "aload": 3, "astore": 3, "jmp": 1, "jz": 2}
BYTECODE = {name: assemble_code(items) for name, items in PROGRAMS.items()}
BC_MAX = (max(len(c) for c in BYTECODE.values()) + 3) & ~3
VARS_OFF = HEAD_LEN + BC_MAX            # variables, then the operand stack; the code follows
CODE_OFF = VARS_OFF + (VARS + STACK_WORDS) * 4
BY_CODE = {c: n for n, (c, _, _) in OPS.items()}
COSTS = bytes(OPS[BY_CODE[i]][2] if i in BY_CODE else 0 for i in range(OPCODE_SLOTS))


def check_contract(path=CONTRACT):
    """Opcode numbers, operand sizes and costs against data/contract.mjs; returns problems, or None without the file."""
    if not path.exists():
        return None
    text = path.read_text()
    found = {}
    for m in re.finditer(r'^\s*\["([A-Z0-9]+)", (\d+), \[(.*?)\], ("argc"|\d+), (\d+), (\d+)', text, re.M):
        sizes = tuple(1 if x == "byte" else 2 for x in re.findall(r"\b(byte|half|word)\(", m.group(3)))
        found[m.group(1)] = (int(m.group(2)), sizes, int(m.group(6)))
    if len(found) < 30:
        return [f"found only {len(found)} opcode rows in {path.name}"]
    return [f"{n}: bench has {OPS[n]}, contract has {found.get(n)}" for n in OPS
            if n not in BENCH_ONLY and found.get(n) != OPS[n]]


# ---- the ARM interpreter --------------------------------------------------------------

def source(variant):
    """Assembler text of the stub. Registers: r4 vpc, r5 operand stack, r6 variables, r7 jump table,
    r8 fuel, r9 operation count (checked), r10 data block, r11 cost table (checked), r12 bytecode base."""
    ck = variant == "checked"
    table = ", ".join(f"op_{BY_CODE[i].lower()}" if i in BY_CODE else "e_bad" for i in range(OPCODE_SLOTS))
    unit = lambda r: f"""
    ldrb {r}, [r4], #1
    ldrb r1, [r4], #1
    orr {r}, {r}, r1, lsl #8"""
    binary = lambda name, body: f"""
op_{name}:
    ldr r1, [r5, #-4]!
    ldr r0, [r5, #-4]
{body}
    str r0, [r5, #-4]
    b loop"""
    compare = lambda name, yes, no: binary(name, f"    cmp r0, r1\n    mov{yes} r0, #1\n    mov{no} r0, #0")
    prologue_end = "    ldr r11, =costs\n    mov r9, #0\n" if ck else ""
    dispatch = """
loop:
    ldrb r0, [r4], #1
    cmp r0, #%d
    bhs e_bad
    ldrb r1, [r11, r0]
    subs r8, r8, r1
    blo e_fuel
    add r9, r9, #1
    tst r9, #255
    beq timecheck
dispatch:
    ldr pc, [r7, r0, lsl #2]""" % OPCODE_SLOTS if ck else """
loop:
    ldrb r0, [r4], #1
    subs r8, r8, #1
    beq e_fuel
    ldr pc, [r7, r0, lsl #2]"""
    timecheck = """
timecheck:
    ldr r1, =TIMER
    ldr r1, [r1, #0x10]
    ldr r2, [r10, #R_START]
    subs r1, r1, r2
    ldrlo r2, [r10, #R_PERIOD]
    addlo r1, r1, r2
    ldr r2, [r10, #IN_LIMIT]
    cmp r1, r2
    bhi e_time
    b dispatch
e_time:
    mov r0, #7
    b exit""" if ck else ""
    costs_table = f"costs:\n    .byte {', '.join(str(c) for c in COSTS)}\n.align 4\n" if ck else ""
    ops_out = "    mov r3, r9" if ck else "    ldr r3, [r10, #IN_FUEL]\n    sub r3, r3, r8"
    return f"""
.equ TIMER, {TIMER:#x}
.equ R_START, {R['start']}
.equ R_END, {R['end']}
.equ R_OPS, {R['ops']}
.equ R_ERR, {R['err']}
.equ R_VPC, {R['vpc']}
.equ R_CPSR, {R['cpsr']}
.equ R_PRD, {R['prd']}
.equ R_TCR, {R['tcr']}
.equ R_PERIOD, {R['period']}
.equ IN_LIMIT, {IN_LIMIT}
.equ IN_FUEL, {IN_FUEL}
.equ IN_N, {IN_N}
.equ HEAD_LEN, {HEAD_LEN}
.equ VARS_OFF, {VARS_OFF}
head:
    b entry
    .space {HEAD_LEN - 4}
bytecode:
    .space {BC_MAX}
vars:
    .space {(VARS + STACK_WORDS) * 4}
entry:
    push {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    ldr r10, =head
    mov r0, #0
    str r0, [r10, #R_OPS]
    add r12, r10, #HEAD_LEN
    .word 0xE10F0000
    str r0, [r10, #R_CPSR]
    ldr r1, =TIMER
    ldr r2, [r1, #0x18]
    str r2, [r10, #R_PRD]
    add r2, r2, #1
    str r2, [r10, #R_PERIOD]
    ldr r2, [r1, #0x20]
    str r2, [r10, #R_TCR]
    add r6, r10, #VARS_OFF
    ldr r0, [r10, #IN_N]
    str r0, [r6]
    mov r0, #0
    add r1, r6, #4
    mov r2, #{VARS - 1}
zero:
    str r0, [r1], #4
    subs r2, r2, #1
    bne zero
    add r5, r6, #{VARS * 4}
    mov r4, r12
    ldr r7, =dispatch_table
    ldr r8, [r10, #IN_FUEL]
{prologue_end}    ldr r1, =TIMER
    ldr r0, [r1, #0x10]
    str r0, [r10, #R_START]
{dispatch}
op_halt:
    mov r0, #0
exit:
    ldr r1, =TIMER
    ldr r2, [r1, #0x10]
    str r2, [r10, #R_END]
    str r0, [r10, #R_ERR]
{ops_out}
    str r3, [r10, #R_OPS]
    sub r3, r4, r12
    str r3, [r10, #R_VPC]
    mov r0, #0
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, pc}}
op_pushb:
    ldrb r0, [r4], #1
    str r0, [r5], #4
    b loop
op_load:{unit("r0")}
    ldr r0, [r6, r0, lsl #2]
    str r0, [r5], #4
    b loop
op_load8:
    ldrb r0, [r4], #1
    ldr r0, [r6, r0, lsl #2]
    str r0, [r5], #4
    b loop
op_store:{unit("r0")}
    ldr r1, [r5, #-4]!
    str r1, [r6, r0, lsl #2]
    b loop
op_store8:
    ldrb r0, [r4], #1
    ldr r1, [r5, #-4]!
    str r1, [r6, r0, lsl #2]
    b loop
op_aload:{unit("r0")}
    ldrb r2, [r4], #1
    ldrb r3, [r4], #1
    orr r2, r2, r3, lsl #8
    ldr r3, [r5, #-4]
    cmp r3, r2
    bhs e_bounds
    add r0, r0, r3
    ldr r0, [r6, r0, lsl #2]
    str r0, [r5, #-4]
    b loop
op_astore:{unit("r0")}
    ldrb r2, [r4], #1
    ldrb r3, [r4], #1
    orr r2, r2, r3, lsl #8
    ldr r1, [r5, #-4]!
    ldr r3, [r5, #-4]!
    cmp r3, r2
    bhs e_bounds
    add r0, r0, r3
    str r1, [r6, r0, lsl #2]
    b loop
op_drop:
    sub r5, r5, #4
    b loop
{binary("add", "    add r0, r0, r1")}
{binary("mul", "    .word 0xE0000190")}
{binary("and", "    and r0, r0, r1")}
{compare("lt", "lt", "ge")}
{compare("gt", "gt", "le")}
op_jmp:{unit("r0")}
    add r4, r12, r0
    b loop
op_jz:{unit("r0")}
    ldr r1, [r5, #-4]!
    cmp r1, #0
    addeq r4, r12, r0
    b loop
e_fuel:
    mov r0, #1
    b exit
e_bad:
    mov r0, #2
    b exit
e_bounds:
    mov r0, #3
    b exit{timecheck}
.pool
.align 4
dispatch_table:
    .word {table}
{costs_table}"""


def build(variant):
    """(image bytes, symbols) of the stub for one variant; refuses an image over the stub area.

    Every Hacktribe write stages its payload at 0xC1000000 before it is copied to its address
    (measured in the emulator), so a write anywhere else would overwrite the start of the stub.
    The image therefore holds what changes between runs first (inputs and results, the bytecode
    slot) and the code last: the host only ever writes at 0xC1000000, a prefix of the image."""
    a = arm.assemble(source(variant), STUB_AT)
    image = a.bytes
    if len(image) > STUB_SIZE:
        raise SystemExit(f"{variant} stub is {len(image)} bytes, over the {STUB_SIZE}-byte stub area")
    assert a.symbols["head"] == STUB_AT and a.symbols["entry"] == STUB_AT + CODE_OFF
    assert image[:4] == TRAMPOLINE
    return image, a.symbols


# Measured in the emulator: the firmware sends the execute ack to the port its parameter names. The value 1 and 2
# pick one port object each (0xC033E5FC, 0xC034040C, see 0xC0027834), every other value sends to both. The first
# device run returned 1 and got no ack over USB; the LED stubs return whatever the last call left in r0.
ACK_PORTS = "r0 = 1: port object 1 only, r0 = 2: port object 2 only, any other value: both"
PROBE_PROGRESS = {0: "the stub never started", 1: "the stub stored its mark", 2: "entered, CPSR and timer registers not read yet",
                  3: "CPSR and timer registers read, counter not read yet", 4: "the stub reached its end",
                  5: "the two-instruction stub stored its mark"}


def probe_source():
    """The two probe stubs, placed at the interpreter's entry offset so that they run where the interpreter will.
    The timer stub reads TGCR, TCR, PRD12 and TIM12 of every timer, spins, and reads TIM12 again."""
    before = "".join(f"    ldr r1, ={base:#x}\n" + "".join(
        f"    ldr r2, [r1, #{reg:#x}]\n    str r2, [r4, #{PROBE_DATA + 20 * i + 4 * k}]\n"
        for k, reg in enumerate((0x24, 0x20, 0x18, 0x10))) for i, (base, _, _) in enumerate(TIMER_LIST))
    after = "".join(f"    ldr r1, ={base:#x}\n    ldr r2, [r1, #0x10]\n    str r2, [r4, #{PROBE_DATA + 20 * i + 16}]\n"
                    for i, (base, _, _) in enumerate(TIMER_LIST))
    return f"""
.equ HEAD, {STUB_AT:#x}
b p_ret
.space {CODE_OFF - 4}
p_ret:
    ldr r1, =HEAD
    mov r2, #1
    str r2, [r1, #{R['prog']}]
    mov r0, #0
    bx lr
.pool
p_timer:
    push {{r4, lr}}
    ldr r4, =HEAD
    mov r2, #2
    str r2, [r4, #{R['prog']}]
    .word 0xE10F0000
    str r0, [r4, #{R['cpsr']}]
{before}    mov r2, #3
    str r2, [r4, #{R['prog']}]
    mov r3, #0x5000
spin:
    subs r3, r3, #1
    bne spin
{after}    mov r2, #4
    str r2, [r4, #{R['prog']}]
    mov r0, #0
    pop {{r4, pc}}
.pool
"""


def build_probes():
    """(image, symbols) of the probe stubs; the first CODE_OFF bytes are the trampoline and a zeroed head block."""
    a = arm.assemble(probe_source(), STUB_AT)
    assert a.symbols["p_ret"] == STUB_AT + CODE_OFF and len(a.bytes) <= STUB_SIZE and a.bytes[:4] == TRAMPOLINE
    return a.bytes, a.symbols


STAGE0 = f"""
    ldr r1, ={STUB_AT:#x}
    mov r2, #5
    str r2, [r1, #{R['prog']}]
    mov r0, #0
    bx lr
"""
TRAMPOLINE = struct.pack("<I", 0xEA000000 | (CODE_OFF - 8) // 4)     # b entry, the first word of every image


def zero_head():
    return TRAMPOLINE + bytes(HEAD_LEN - 4)


def with_program(image, program):
    return image[:HEAD_LEN] + BYTECODE[program].ljust(BC_MAX, b"\0") + image[HEAD_LEN + BC_MAX:]


def head_block(limit_ticks, fuel, n):
    """Inputs of one run; the results are zeroed so that a run that did not happen shows."""
    block = bytearray(zero_head())
    block[IN_LIMIT:IN_LIMIT + 8] = struct.pack("<II", limit_ticks, fuel)
    block[IN_N:IN_N + 4] = struct.pack("<I", n)
    return bytes(block)


def parse_head(raw):
    return {k: struct.unpack_from("<I", raw, off)[0] for k, off in R.items()}


def where(head, probe):
    """Where a stub that gave no ack got to, from the words it left in the head block; `probe` is the
    final progress word of a probe stub, or None for the interpreter."""
    if probe:
        done = ": it finished, only the ack is missing (lost, or sent to another port: ACK_PORTS)" if head["prog"] == probe else ""
        return f"progress word {head['prog']}, {PROBE_PROGRESS.get(head['prog'], 'unknown value')}{done}"
    if head["ops"]:
        return (f"ran to its exit ({head['ops']} operations, error {head['err']}): the stub finished, only the ack is missing "
                "(lost, or sent to another port: ACK_PORTS)")
    if not head["cpsr"]:
        return "no result field was written: the stub never started, or stopped in its first instructions"
    if not (head["prd"] or head["tcr"]):
        return "entered (CPSR stored), stopped before the timer registers were read"
    return (f"timer registers read (period {head['prd'] + 1}, control {head['tcr']:#x}, counter {head['start']}), "
            "stopped inside the interpreter before it exited")


def parse_results(raw):
    """Results and variables from the read of STUB_AT .. STUB_AT + VARS_OFF + 4 * VARS."""
    out = parse_head(raw)
    out["vars"] = list(struct.unpack_from(f"<{VARS}I", raw, VARS_OFF))
    return out


# ---- the link to the device ------------------------------------------------------------


BARE_TIMERS = {0x01C20000: (23999, 5), 0x01C21000: (0x16E35FF, 0xB), 0x01F0C000: (0x124F7, 5), 0x01F0D000: (0x8F0D17F, 5)}


class BareLink:
    """The stub alone in Unicorn: no firmware, a timer that counts 5 ns per instruction like the emulator."""
    NS_PER_INSN = 5

    def __init__(self):
        import unicorn
        from unicorn import arm_const
        self.u, self.k = unicorn, arm_const
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(STUB_AT, 0x1000)
        self.uc.mem_map(STUB_AT + 0x100000, 0x1000)
        self.insns = 0
        for base, hz, _ in TIMER_LIST:
            self.uc.mmio_map(base, 0x1000, self._read, (base, hz), None, None)
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self._count, begin=STUB_AT, end=STUB_AT + 0xFFF)

    def _count(self, uc, addr, size, user):
        self.insns += 1

    def _read(self, uc, off, size, user):
        base, hz = user
        prd, tgcr = BARE_TIMERS[base]
        ticks = int(self.insns * self.NS_PER_INSN * hz / 1e9) % (prd + 1) if (tgcr >> 2) & 3 != 2 else 0
        return {0x10: ticks, 0x18: prd, 0x20: 0x80, 0x24: tgcr}.get(off, 0)

    def read(self, addr, length):
        return bytes(self.uc.mem_read(addr, length))

    def write(self, addr, data, verify=True):
        self.uc.mem_write(addr, bytes(data))
        self.uc.ctl_flush_tb()          # host writes do not invalidate translated code

    def execute(self, addr):
        if addr == ICACHE_INVALIDATE:
            return
        self.insns = 0
        ret = STUB_AT + 0x100000
        self.uc.reg_write(self.k.UC_ARM_REG_SP, STUB_AT + 0x100800)
        self.uc.reg_write(self.k.UC_ARM_REG_LR, ret)
        self.uc.emu_start(addr, ret)
        self.last_insns = self.insns
        if self.uc.reg_read(self.k.UC_ARM_REG_R0) != 0:
            raise SystemExit("the stub did not return 0")


def emulator_link(vsb):
    """Device over the emulated DIN-MIDI of the firmware, counting the stub's instructions."""
    from led_show import Device, emulator_ask
    import unicorn
    ask, m = emulator_ask(vsb)
    dev = Device(ask)
    dev.insns = 0

    def count(uc, addr, size, user):
        dev.insns += 1
    m.uc.hook_add(unicorn.UC_HOOK_CODE, count, begin=STUB_AT, end=STUB_AT + STUB_SIZE - 1)
    plain = dev.execute

    def execute(addr):
        dev.insns = 0
        plain(addr)
        if addr != ICACHE_INVALIDATE:
            dev.last_insns = dev.insns
    dev.execute = execute
    dev.last_insns = None
    return dev, m


# ---- the run ----------------------------------------------------------------------------

def elapsed(start, end, prd):
    d = end - start
    return d if d >= 0 else d + (prd + 1 if prd != 0xFFFFFFFF else 1 << 32)


def fit(xs, ys):
    """Least squares y = a + b x; (a, b)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return my - b * mx, b


class StageFailed(Exception):
    pass


LOST = ("no answer", "no write ack", "unexpected reply")     # what led_show.py raises when a reply does not come


class Bench:
    def __init__(self, dev, symbols, args):
        self.dev, self.args = dev, args
        self.entry = STUB_AT
        self.window = (STUB_AT, STUB_AT + STUB_SIZE)
        self.info = None
        self.alias = None
        self.image = None

    def retrying(self, label, fn):
        """Run one SysEx exchange again after a lost reply, with growing pauses; other failures pass through."""
        tries = getattr(self.args, "retries", 0)
        for i in range(tries + 1):
            try:
                return fn()
            except SystemExit as e:
                msg = str(e.code)
                if i == tries or not any(m in msg for m in LOST):
                    raise
                wait = getattr(self.args, "retry_pause", 0.0) * 2 ** i
                print(f"  {label}: {msg}; retry {i + 1} of {tries} after {wait:g} s")
                time.sleep(wait)

    def read(self, addr, length):
        return self.retrying(f"read {addr:#x}", lambda: self.dev.read(addr, length))

    def put(self, addr, data, verify=True):
        if not (self.window[0] <= addr and addr + len(data) <= self.window[1]):
            raise SystemExit(f"refusing to write {addr:#x}+{len(data)}: outside the stub area")
        if addr != STUB_AT:
            raise SystemExit(f"refusing to write at {addr:#x}: Hacktribe stages every write at {STUB_AT:#x}")
        self.retrying(f"write {addr:#x}", lambda: self.dev.write(addr, data, verify))
        time.sleep(getattr(self.args, "pause", 0.0))

    def alias_works(self):
        """Whether 0xC4000000 shows the same RAM as 0xC0000000: the firmware code reads back identically through it."""
        if self.alias is None:
            (addr, length), digest = next(iter(EXPECTED.items()))
            try:
                self.alias = hashlib.sha256(self.read(addr + ALIAS, length)).hexdigest() == digest
            except SystemExit:
                self.alias = False
        return self.alias

    def evict(self):
        for off in range(0, getattr(self.args, "evict_kib", 0) * 1024, EVICT_STEP):
            self.read(EVICT_AT + off, EVICT_STEP)

    def make_coherent(self, data, start=0):
        """Make RAM, which the instruction fetch reads, hold data[start:] at STUB_AT + start; the read-back of a
        write goes through the data cache and cannot show it."""
        if not getattr(self.args, "caches", False):
            return
        kib = getattr(self.args, "evict_kib", 0)
        if not self.alias_works():
            print("  RAM view not checkable (no uncached alias at 0xC4000000)" + ("; pushing the cache out blind" if kib else ""))
            self.evict()
            return
        want = data[start:]
        for attempt in range(4):
            ram = self.read(STUB_AT + ALIAS + start, len(want))
            if ram == want:
                print(f"  RAM view equals the written image{' after pushing the cache out' if attempt else ''}")
                return
            bad = sum(a != b for a, b in zip(ram, want))
            print(f"  RAM view differs from the written image in {bad} of {len(want)} bytes: the data cache holds the newer copy"
                  + (f"; reading {kib} KiB to push it out" if kib else ""))
            if not kib:
                break
            self.evict()
        raise StageFailed("RAM never matched the written image; nothing executed")

    def invalidate(self):
        """The firmware's instruction cache invalidation, again after a lost ack: it can run twice."""
        tries = getattr(self.args, "retries", 0)
        for i in range(tries + 1):
            try:
                self.dev.execute(ICACHE_INVALIDATE)
                return
            except SystemExit as e:
                if i == tries:
                    raise StageFailed(f"the instruction cache invalidation got no ack ({e.code}); nothing executed")
                wait = getattr(self.args, "retry_pause", 0.0) * 2 ** i
                print(f"  invalidate: {e.code}; retry {i + 1} of {tries} after {wait:g} s")
                time.sleep(wait)

    def upload(self, image):
        """Write a stub image, bring RAM in line, then drop the instruction cache."""
        self.image = image
        self.put(STUB_AT, image)
        self.make_coherent(image)
        self.invalidate()

    def read_head(self):
        try:
            return parse_head(self.read(STUB_AT, HEAD_LEN))
        except SystemExit as e:
            raise StageFailed(f"the head block could not be read either ({e.code})")

    def execute(self, entry, label, probe=None):
        """One execute. A lost ack is not a failure when the stub left its end mark (probe: the final progress
        word, interpreter: a nonzero operation count, which the stub clears at its start); a stub that did not
        run is executed again after a pause, once the code in RAM has been checked again. The caller clears the
        marks before the first execute."""
        tries = getattr(self.args, "retries", 0)
        for i in range(tries + 1):
            try:
                self.dev.execute(entry)
                return
            except SystemExit as e:
                why = e.code
            print(f"  {label}: execute at {entry:#x} got no ack ({why})")
            time.sleep(getattr(self.args, "settle", 0.0))
            head = self.read_head()
            print(f"  {where(head, probe)}")
            print("  head block: " + " ".join(f"{k} {v:#x}" for k, v in head.items()))
            if (head["prog"] == probe) if probe else head["ops"]:
                print("  the stub finished and only its ack was lost; going on")
                return
            if i == tries:
                raise StageFailed(f"{label}: no ack after {tries + 1} tries; {where(head, probe)}")
            wait = getattr(self.args, "retry_pause", 0.0) * 2 ** i
            print(f"  the stub did not run; retry {i + 1} of {tries} after {wait:g} s")
            time.sleep(wait)
            if self.image is not None:
                self.make_coherent(self.image, CODE_OFF if len(self.image) > CODE_OFF else 0)

    def prepare(self, variant, image):
        self.variant = variant
        self.upload(image)

    def set_program(self, name):
        self.program = name
        self.put(STUB_AT, zero_head() + BYTECODE[name].ljust(BC_MAX, b"\0"))

    def run_once(self, n, ref):
        """Execute the stub once for size n and return the checked result."""
        self.execute(self.entry, f"{self.variant}/{self.program} n={n}")
        w = parse_results(self.read(STUB_AT, VARS_OFF + VARS * 4))
        if w["err"]:
            raise SystemExit(f"{self.variant}/{self.program} n={n}: stub stopped with {ERRORS.get(w['err'], w['err'])} at bytecode offset {w['vpc']}")
        if w["vars"] != ref["vars"] or w["ops"] != ref["ops"]:
            raise SystemExit(f"{self.variant}/{self.program} n={n}: result differs from the reference: "
                             f"ops {w['ops']} vs {ref['ops']}, variables {w['vars']} vs {ref['vars']}")
        ticks = elapsed(w["start"], w["end"], w["prd"])
        if ticks == 0 and w["ops"] > 100:
            raise SystemExit(f"the counter at {TIMER + 0x10:#x} did not advance during the run; stopping")
        return {"ticks": ticks, "ops": w["ops"], "prd": w["prd"],
                "tcr": w["tcr"], "cpsr": w["cpsr"], "insns": getattr(self.dev, "last_insns", None)}

    def measure(self, n):
        code = BYTECODE[self.program]
        ref = reference(code, n)
        fuel = int((ref["cost"] if self.variant == "checked" else ref["ops"]) * 1.5) + 64
        self.put(STUB_AT, head_block(int(self.args.limit_ms * 1e6 / TICK_NS), fuel, n))
        runs = [self.run_once(n, ref) for _ in range(self.args.repeat)]
        best = min(runs, key=lambda r: r["ticks"])
        if self.info is None:
            self.info = best
        return {"n": n, "ops": ref["ops"], "cost": ref["cost"], "hist": ref["hist"], "ticks": best["ticks"],
                "all": sorted(r["ticks"] for r in runs), "insns": best["insns"]}

    def sizes(self, ops_per_iter):
        """Sizes for the ladder: a tiny first run sets the pace, then 1/8, 1/4, 1/2 and 1 of the target time."""
        out = [self.measure(max(1, 300 // ops_per_iter))]
        if self.info["cpsr"] & 0x80 and not self.args.bare and self.args.target_ms > 2:
            print(f"  IRQ is masked while the stub runs: a long run would stall the 1 kHz tick; target lowered from {self.args.target_ms} ms to 2 ms")
            self.args.target_ms = 2.0
        for part in (0.125, 0.25, 0.5, 1.0):
            r = out[-1]
            ns_per_op = max(r["ticks"], 1) * TICK_NS / r["ops"]
            grown = int(part * self.args.target_ms * 1e6 / ns_per_op / ops_per_iter)
            n = max(out[-1]["n"] + 1, min(grown, out[-1]["n"] * 8))
            if out[-1]["ticks"] * TICK_NS > self.args.target_ms * 1e6 * 3:
                print(f"    {self.program}: a run took more than three times the target, ladder stops")
                break
            out.append(self.measure(n))
        return out


def summarize(runs, tick_ns=None):
    """Cost per operation from the ladder, as ticks against operations: ns per operation, fixed ns, and the
    instructions per operation when known. A round is the operations per iteration, so ns per round is the
    figure that probes are compared by."""
    ops = [r["ops"] for r in runs]
    fixed, per_op = fit(ops, [r["ticks"] * (tick_ns or TICK_NS) for r in runs])
    ins = fit(ops, [r["insns"] for r in runs]) if all(r["insns"] is not None for r in runs) else None
    ops_iter = fit([r["n"] for r in runs], ops)[1]
    return {"ns_op": per_op, "fixed_ns": fixed, "ops_iter": ops_iter, "ns_iter": per_op * ops_iter,
            "insn_op": ins[1] if ins else None, "insn_iter": ins[1] * ops_iter if ins else None}


def report(label, results):
    print(f"\n{label}")
    print(f"  {'program':8} {'ops/round':>9} {'ns/round':>9} {'ns/op':>7} {'fixed ns':>9} {'insn/op':>8} {'ns/insn':>8}  sizes (N), min of runs")
    base = results.get("count")
    for name, runs in results.items():
        s = summarize(runs)
        insn = s["insn_op"]
        sizes = " ".join(f"{r['n']}" for r in runs)
        print(f"  {name:8} {s['ops_iter']:9.2f} {s['ns_iter']:9.1f} {s['ns_op']:7.1f} {s['fixed_ns']:9.0f} "
              f"{'' if insn is None else format(insn, '8.2f'):>8} {'' if insn is None else format(s['ns_op'] / insn, '8.2f'):>8}  {sizes}")
    if base:
        b = summarize(base)
        print(f"  one pair of operations, from the difference to count ({COPIES} copies per round):")
        for name, k in UNIT_OPS.items():
            if name in results:
                s = summarize(results[name])
                ns = (s["ns_iter"] - b["ns_iter"]) / COPIES
                ins = None if s["insn_iter"] is None else (s["insn_iter"] - b["insn_iter"]) / COPIES
                extra = "" if ins is None else f", {ins:.2f} instructions, {ns / ins:.2f} ns each" if ins else ""
                print(f"    {name:8} {ns:7.1f} ns for {k} operation(s), {ns / k:6.1f} ns each{extra}")
        for wide, narrow in (("load", "load8"), ("store", "store8")):
            if wide in results and narrow in results:
                a, c = summarize(results[wide]), summarize(results[narrow])
                print(f"    16-bit operand surcharge, {wide} against {narrow}: {(a['ns_iter'] - c['ns_iter']) / COPIES:.1f} ns per operation")
    if "mix" in results:
        hist = results["mix"][-1]["hist"]
        total = sum(hist.values())
        share = lambda *n: 100 * sum(hist.get(x, 0) for x in n) / total
        print(f"  mix: {share('LOAD', 'STORE'):.1f} % LOAD/STORE, {share('ALOAD', 'ASTORE'):.1f} % ALOAD/ASTORE (Snake: 30.4 and 6.2)")


def compare(results, other, other_tick_ns):
    print("\nfactor to the emulator run (device ns per round / emulator ns per round, and ns per emulator instruction)")
    for variant, progs in results.items():
        for name, runs in progs.items():
            theirs = other.get(variant, {}).get(name)
            if not theirs:
                continue
            a, b = summarize(runs), summarize(theirs, other_tick_ns)
            ins = f", {a['ns_iter'] / b['insn_iter']:.2f} ns per instruction" if b["insn_iter"] else ""
            print(f"  {variant:8} {name:8} x{a['ns_iter'] / b['ns_iter']:6.2f}{ins}")


def check_firmware(bench):
    for (addr, length), digest in EXPECTED.items():
        if hashlib.sha256(bench.read(addr, length)).hexdigest() != digest:
            raise SystemExit(f"code at {addr:#x} differs from the measured build; nothing written")


def parse_timers(raw):
    """Rows of the stage 2 table from the read of STUB_AT .. STUB_AT + PROBE_DATA + 20 * len(TIMER_LIST)."""
    rows = []
    for i, (base, hz, name) in enumerate(TIMER_LIST):
        tgcr, tcr, prd, before, after = struct.unpack_from("<5I", raw, PROBE_DATA + 20 * i)
        rows.append({"base": base, "hz": hz, "name": name, "tgcr": tgcr, "tcr": tcr, "prd": prd,
                     "ticks": elapsed(before, after, prd) if before or after else 0})
    return rows


def pick_timer(rows):
    """(row, hz, notes): the running counter with the highest clock whose wrap is at least MIN_WRAP_MS away, or None.
    A clock that differs from its nominal value by more than 5 % against the 24 MHz counter of timer 0 is replaced
    by the measured one."""
    notes = []
    ref = rows[0] if rows[0]["ticks"] and rows[0]["ticks"] < rows[0]["prd"] + 1 else None
    best = None
    for r in rows:
        r["hz_used"] = r["hz"]
        if ref and r is not ref and r["ticks"]:
            measured = ref["hz"] * r["ticks"] / ref["ticks"]
            if abs(measured / r["hz"] - 1) > 0.05:
                notes.append(f"{r['name']}: {r['ticks']} ticks against {ref['ticks']} of the 24 MHz counter, so {measured / 1e6:.1f} MHz, not {r['hz'] / 1e6:.0f}")
                r["hz_used"] = measured
        r["wrap_ms"] = (r["prd"] + 1) / r["hz_used"] * 1e3
        r["usable"] = bool(r["ticks"]) and r["wrap_ms"] >= MIN_WRAP_MS
        if r["usable"] and (best is None or r["hz_used"] > best["hz_used"]):
            best = r
    if not ref:
        notes.append("timer 0 did not give a usable reading, so the clock rates are the assumed ones")
    return best, notes


def run_stages(bench, probes, stub, args):
    """Four executes in rising order of what they ask of the device; a failing one raises StageFailed."""
    image, symbols = probes
    print("stage 0: a stub at 0xC1000000 that stores a mark and returns 0, like the LED stubs")
    bench.upload(arm.assemble(STAGE0, STUB_AT).bytes.ljust(HEAD_LEN, b"\0"))
    bench.execute(STUB_AT, "stage 0", probe=5)
    head = bench.read_head()
    if head["prog"] != 5:
        raise StageFailed(f"stage 0: acked but {where(head, 5)}")
    print("  ok")
    print("stage 1: the mark stub at the interpreter's entry offset, executed there directly")
    bench.upload(image)
    bench.execute(symbols["p_ret"], "stage 1", probe=1)
    head = bench.read_head()
    if head["prog"] != 1:
        raise StageFailed(f"stage 1: acked but {where(head, 1)}")
    print("  ok")
    print("stage 2: CPSR, then TGCR, TCR, PRD12 and TIM12 of every timer before and after a short spin")
    bench.put(STUB_AT, zero_head() + bytes(CODE_OFF - HEAD_LEN))
    bench.execute(symbols["p_timer"], "stage 2", probe=4)
    head = bench.read_head()
    if head["prog"] != 4:
        raise StageFailed(f"stage 2: acked but {where(head, 4)}")
    mode = {0x10: "USR", 0x11: "FIQ", 0x12: "IRQ", 0x13: "SVC", 0x17: "ABT", 0x1B: "UND", 0x1F: "SYS"}.get(head["cpsr"] & 0x1F, "?")
    print(f"  cpsr {head['cpsr']:#x} ({mode}, IRQ {'masked' if head['cpsr'] & 0x80 else 'enabled'})")
    rows = parse_timers(bench.read(STUB_AT, PROBE_DATA + 20 * len(TIMER_LIST)))
    best, notes = pick_timer(rows)
    for r in rows:
        print(f"  {r['base']:#x} {r['name']:30} TGCR {r['tgcr']:#x} TCR {r['tcr']:#x} period {r['prd'] + 1} "
              f"advanced {r['ticks']} ticks" + ("" if r["ticks"] else " (not running)")
              + (f", wraps every {r['wrap_ms']:.2f} ms" if r.get("wrap_ms") else ""))
    for n in notes:
        print("  note: " + n)
    if not best:
        raise StageFailed("stage 2: no counter ran with a wrap of at least %d ms; a coarse source is left (the 1 kHz tick), "
                          "too coarse for a 2 ms run" % MIN_WRAP_MS)
    select_timer(best["base"], best["hz_used"])
    print(f"  ok: counter {best['base'] + 0x10:#x} at {best['hz_used'] / 1e6:.1f} MHz is used")
    stub = build(args.variants[0])
    variant = args.variants[0]
    print(f"stage 3: the {variant} interpreter, program count, N = 1, through the trampoline")
    bench.prepare(variant, with_program(stub[0], "count"))
    bench.program = "count"
    ref = reference(BYTECODE["count"], 1)
    bench.put(STUB_AT, head_block(int(args.limit_ms * 1e6 / TICK_NS), ref["ops"] * 2 + 64, 1))
    bench.run_once(1, ref)
    print("  ok")


def run(dev, args):
    stubs = {v: build(v) for v in args.variants}
    for v, (image, _) in stubs.items():
        print(f"{v}: stub {len(image)} bytes of {STUB_SIZE}, bytecode slot {BC_MAX}, programs "
              + ", ".join(f"{n} {len(c)}" for n, c in BYTECODE.items()))
    bench = Bench(dev, None, args)
    if not args.bare:
        check_firmware(bench)
    probes = build_probes()
    length = max([len(image) for image, _ in stubs.values()] + [len(probes[0])])
    original = bench.read(STUB_AT, length)
    print(("checks passed: firmware code matches, " if not args.bare else "") + f"{length} bytes at {STUB_AT:#x} saved")
    if args.dry_run:
        print("dry run: nothing written")
        return {}
    results, info, failure = {}, None, None
    try:
        if args.stages:
            run_stages(bench, probes, stubs[args.variants[0]], args)
            stubs = {v: build(v) for v in args.variants}
        else:
            print(f"timer not checked: counter {TIMER + 0x10:#x} is assumed")
        for variant, (image, symbols) in stubs.items():
            if args.stages_only:
                break
            bench = Bench(dev, symbols, args)
            bench.prepare(variant, with_program(image, args.programs[0]))
            results[variant] = {}
            for name in args.programs:
                bench.set_program(name)
                ops_iter = reference(BYTECODE[name], 100)["ops"] - reference(BYTECODE[name], 50)["ops"]
                results[variant][name] = bench.sizes(ops_iter // 50)
                if info is None and bench.info:
                    info = bench.info
                    mode = {0x10: "USR", 0x11: "FIQ", 0x12: "IRQ", 0x13: "SVC", 0x17: "ABT", 0x1B: "UND", 0x1F: "SYS"}.get(info["cpsr"] & 0x1F, "?")
                    print(f"cpsr {info['cpsr']:#x}: {mode} mode, IRQ {'masked' if info['cpsr'] & 0x80 else 'enabled'}, "
                          f"timer period {info['prd'] + 1} ticks, control {info['tcr']:#x}")
                    if info["tcr"] >> 6 & 3 != 2:
                        print("  warning: the timer is not in continuous mode")
                print(f"  {variant}/{name}: " + ", ".join(f"N={r['n']} {r['ticks'] * TICK_NS / 1000:.0f} us" for r in results[variant][name]))
    except StageFailed as e:
        failure = e
    finally:
        time.sleep(0.2)
        bench.image = None
        try:
            bench.put(STUB_AT, original)
            bench.make_coherent(original)
            print("original bytes at the stub address restored")
        except StageFailed as e:
            print(f"  warning: {e}")
        except SystemExit as e:
            print(f"  RESTORE FAILED ({e.code}): the stub bytes are still at {STUB_AT:#x}; rerun a script that restores them, "
                  "or restart the device")
            failure = failure or StageFailed("restore failed")
    if failure:
        print(f"stopped: {failure}")
        raise SystemExit(2)
    for variant, progs in results.items():
        report(f"== {variant} ==", progs)
    if args.compare:
        theirs = json.loads(Path(args.compare).read_text())
        compare(results, theirs["results"], theirs.get("tick_ns", 1000 / 24))
    return results


def dump_programs():
    """Bytecode and reference results of every program, for the JS VM cross check in test/vm-bench.test.mjs."""
    out = {}
    for name, code in BYTECODE.items():
        out[name] = {"code": code.hex(), "bench_only": bool(BENCH_ONLY & {i[0] for i in PROGRAMS[name] if not isinstance(i, str)}),
                     "cases": [{"n": n, **{k: v for k, v in reference(code, n).items() if k != "hist"}} for n in (0, 1, 5, 37)]}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--emu", metavar="VSB", help="run against the firmware in the emulator")
    p.add_argument("--bare", action="store_true", help="run the stub alone in Unicorn, without firmware")
    p.add_argument("--dry-run", action="store_true", help="checks only, writes nothing")
    p.add_argument("--variants", default="lean,checked")
    p.add_argument("--programs", default=",".join(PROGRAMS))
    p.add_argument("--repeat", type=int)
    p.add_argument("--no-stages", dest="stages", action="store_false", help="skip the staged executes before the benchmark")
    p.add_argument("--stages-only", action="store_true", help="run the staged executes and stop")
    p.add_argument("--evict-kib", type=int, help="KiB of firmware code read to push the data cache out (default 128 on the device, else 0)")
    p.add_argument("--settle", type=float, default=2.0, help="seconds to wait after a missing ack before reading the progress words")
    p.add_argument("--retries", type=int, default=3, help="repeat a write, read or execute this often after a lost reply")
    p.add_argument("--retry-pause", type=float, default=1.5, help="seconds before the first repeat, doubled each time")
    p.add_argument("--pause", type=float, help="seconds after each write, before anything is executed (default 0.3 on the device, else 0)")
    p.add_argument("--target-ms", type=float, help="time of the longest run (default 10 on the device, 2 otherwise)")
    p.add_argument("--limit-ms", type=float, default=40, help="the checked stub stops a run after this long")
    p.add_argument("--json", metavar="FILE")
    p.add_argument("--compare", metavar="FILE", help="a --json file of an emulator run")
    p.add_argument("--check-contract", action="store_true")
    p.add_argument("--dump-programs", action="store_true")
    a = p.parse_args()
    if a.check_contract:
        problems = check_contract()
        if problems is None:
            raise SystemExit(f"{CONTRACT} not found, opcode numbers not cross-checked")
        print("\n".join(problems) or "opcode numbers, operand sizes and costs match the contract")
        raise SystemExit(1 if problems else 0)
    if a.dump_programs:
        print(json.dumps(dump_programs()))
        return
    problems = check_contract()
    if problems:
        raise SystemExit("bench opcode table differs from the contract:\n" + "\n".join(problems))
    a.variants = a.variants.split(",")
    a.programs = a.programs.split(",")
    unknown = [x for x in a.variants if x not in ("lean", "checked")] + [x for x in a.programs if x not in PROGRAMS]
    if unknown:
        raise SystemExit(f"unknown variant or program: {unknown}")
    on_device = not (a.emu or a.bare)
    a.target_ms = a.target_ms if a.target_ms is not None else (10.0 if on_device else 2.0)
    a.repeat = a.repeat or (5 if on_device else 2)
    a.caches = on_device
    a.pause = a.pause if a.pause is not None else (0.3 if on_device else 0.0)
    a.evict_kib = a.evict_kib if a.evict_kib is not None else (128 if on_device else 0)
    if a.stages_only and not a.stages:
        raise SystemExit("--stages-only and --no-stages exclude each other")
    if a.target_ms > 40 or a.limit_ms > 60:
        raise SystemExit("--target-ms above 40 or --limit-ms above 60 could disturb audio and MIDI; refused")
    m = None
    if a.bare:
        dev = BareLink()
    elif a.emu:
        dev, m = emulator_link(a.emu)
    else:
        from led_show import Device, mido_ask
        dev = Device(mido_ask())
    results = run(dev, a)
    if m is not None:
        m.run_until(m.time_ns / 1e9 + 0.5)
        print("emulator asserts:", m.asserts)
    if a.json and results:
        Path(a.json).write_text(json.dumps({"mode": "device" if on_device else "emulator" if a.emu else "bare",
                                            "target_ms": a.target_ms, "repeat": a.repeat, "tick_ns": TICK_NS, "results": results}, indent=1))
        print(f"results written to {a.json}")


if __name__ == "__main__":
    main()
